"""LangGraph orchestration for the Job Application Agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from langgraph.graph import END, StateGraph

from agent.nodes import (
    error_handler_node,
    export_output_node,
    generate_cover_letters_node,
    match_jobs_node,
    scrape_jobs_node,
)
from agent.state import AgentState
from resume.parser import parse_resume

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _route_on_errors(state: AgentState, next_node: str) -> Literal["error_handler"] | str:
    """Route to error handler when state contains errors.

    Args:
        state: Current graph state.
        next_node: Node to continue to when there are no errors.

    Returns:
        Name of the next node.
    """

    return "error_handler" if len(state.get("errors", [])) > 0 else next_node


def _route_after_export(state: AgentState) -> Literal["error_handler", "__end__"]:
    """Route after export.

    Args:
        state: Current graph state.

    Returns:
        Error handler node or graph end marker.
    """

    return "error_handler" if len(state.get("errors", [])) > 0 else END


graph = StateGraph(AgentState)
graph.add_node("scrape_jobs", scrape_jobs_node)
graph.add_node("match_jobs", match_jobs_node)
graph.add_node("generate_cover_letters", generate_cover_letters_node)
graph.add_node("export_output", export_output_node)
graph.add_node("error_handler", error_handler_node)
graph.set_entry_point("scrape_jobs")
graph.add_conditional_edges("scrape_jobs", lambda state: _route_on_errors(state, "match_jobs"))
graph.add_conditional_edges("match_jobs", lambda state: _route_on_errors(state, "generate_cover_letters"))
graph.add_conditional_edges("generate_cover_letters", lambda state: _route_on_errors(state, "export_output"))
graph.add_conditional_edges("export_output", _route_after_export)
graph.add_edge("error_handler", END)
app_graph = graph.compile()


def run_agent(
    resume_path: str,
    job_title: str,
    location: str,
    candidate_name: str,
    max_results: int,
    threshold: float,
) -> AgentState:
    """Run the complete job application agent.

    Args:
        resume_path: Path to uploaded PDF or DOCX resume.
        job_title: Target job title.
        location: Target location.
        candidate_name: Candidate full name.
        max_results: Maximum results per source.
        threshold: Semantic relevance threshold.

    Returns:
        Final AgentState after graph execution.
    """

    parsed_resume = parse_resume(resume_path)
    output_path = str(Path("output") / "applications.json")
    initial_state: AgentState = {
        "resume_text": str(parsed_resume["raw_text"]),
        "resume_skills": [],
        "job_listings": [],
        "matched_jobs": [],
        "cover_letters": [],
        "output_json": [],
        "errors": [],
        "status": "initialized",
        "job_title": job_title,
        "location": location,
        "candidate_name": candidate_name,
        "max_results": max_results,
        "threshold": threshold,
        "output_path": output_path,
    }
    logger.info("Invoking agent graph")
    return app_graph.invoke(initial_state)

