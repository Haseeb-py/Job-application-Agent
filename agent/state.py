"""Typed state definition shared by the LangGraph job application agent."""

from typing import Any, TypedDict


class AgentState(TypedDict):
    """Mutable state passed between LangGraph nodes.

    Args:
        resume_text: Raw parsed resume content.
        resume_skills: Skills extracted from the resume text.
        job_listings: Raw scraped jobs from all configured sources.
        matched_jobs: Jobs filtered by semantic relevance.
        cover_letters: Generated cover letters and skill gap metadata.
        output_json: Final application payload records.
        errors: Pipeline errors and warnings.
        status: Current pipeline stage label.
    """

    resume_text: str
    resume_skills: list[str]
    job_listings: list[dict[str, Any]]
    matched_jobs: list[dict[str, Any]]
    cover_letters: list[dict[str, Any]]
    output_json: list[dict[str, Any]]
    errors: list[str]
    status: str
    job_title: str
    location: str
    candidate_name: str
    max_results: int
    threshold: float
    output_path: str
