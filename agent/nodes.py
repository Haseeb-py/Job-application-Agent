"""LangGraph node functions for the autonomous job application workflow."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from typing import Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agent.prompts import cover_letter_prompt
from agent.state import AgentState
from matcher.semantic_match import semantic_match
from storage.exporter import save_to_json
from resume.skill_gap import analyze_gap, extract_skills
from scraper.glassdoor_scraper import scrape_glassdoor_jobs
from scraper.linkedin_scraper import scrape_linkedin_jobs
from scraper.utils import deduplicate_jobs

load_dotenv()
logger = logging.getLogger(__name__)


def _merge_state(state: AgentState, **updates: Any) -> dict[str, Any]:
    """Create a LangGraph-compatible partial state update.

    Args:
        state: Current agent state.
        updates: Updated field values.

    Returns:
        Partial state dictionary.
    """

    merged = dict(state)
    merged.update(updates)
    return merged


@retry(wait=wait_exponential(min=1, max=60), stop=stop_after_attempt(5), retry=retry_if_exception_type(Exception))
def _call_groq(prompt_text: str) -> str:
    """Call Groq LLM with retry/backoff.

    Args:
        prompt_text: Fully rendered cover letter prompt.

    Returns:
        Generated cover letter text.
    """

    groq_api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    groq_model = (os.getenv("GROQ_MODEL") or "llama-3.1-8b-instant").strip()
    llm = ChatGroq(model=groq_model, temperature=0.3, api_key=groq_api_key)
    response = llm.invoke(prompt_text)
    return str(response.content).strip()


def _fallback_cover_letter(job: dict[str, Any], state: AgentState, gap: dict[str, Any]) -> str:
    """Create a local fallback cover letter when LLM generation fails.

    Args:
        job: Matched job dictionary.
        state: Current agent state.
        gap: Skill gap analysis for the job.

    Returns:
        Three-paragraph fallback cover letter.
    """

    candidate_name = state.get("candidate_name") or "Candidate"
    role = job.get("job_title") or "the role"
    company = job.get("company") or "your company"
    skills = ", ".join(gap.get("matching_skills", [])) or ", ".join(state.get("resume_skills", [])[:6]) or "relevant technical skills"
    return (
        f"Dear Hiring Team,\n\n"
        f"I am excited to apply for the {role} position at {company}. My background includes {skills}, "
        f"which aligns well with the responsibilities described for this opportunity.\n\n"
        f"I am especially interested in this role because it offers a chance to apply practical engineering, "
        f"problem-solving, and delivery-focused experience to work that can create measurable impact. I bring a careful, "
        f"hands-on approach to learning requirements, building reliable solutions, and improving systems over time.\n\n"
        f"Thank you for considering my application. I would welcome the opportunity to discuss how my skills and experience "
        f"can contribute to {company}.\n\n"
        f"Sincerely,\n{candidate_name}"
    )


def scrape_jobs_node(state: AgentState) -> dict[str, Any]:
    """Scrape jobs from LinkedIn and Glassdoor.

    Args:
        state: Current agent state.

    Returns:
        Updated state fields.
    """

    errors = list(state.get("errors", []))
    scraper_errors: list[str] = []
    job_title = state.get("job_title") or "Software Engineer"
    location = state.get("location") or ""
    max_results = int(state.get("max_results") or 20)
    logger.info("Starting scrape for %s in %s", job_title, location)

    linkedin_jobs = scrape_linkedin_jobs(job_title, location, max_results=max_results, errors=scraper_errors)
    glassdoor_jobs = scrape_glassdoor_jobs(job_title, location, max_results=max_results, errors=scraper_errors)
    jobs = deduplicate_jobs(linkedin_jobs + glassdoor_jobs)
    if jobs:
        for error in scraper_errors:
            logger.warning("Non-fatal scraper warning: %s", error)
    else:
        errors.extend(scraper_errors)
    return _merge_state(state, status="scraping", job_listings=jobs, errors=errors)


def match_jobs_node(state: AgentState) -> dict[str, Any]:
    """Extract resume skills and semantically match jobs.

    Args:
        state: Current agent state.

    Returns:
        Updated state fields.
    """

    errors = list(state.get("errors", []))
    resume_skills = extract_skills(state.get("resume_text", ""))
    matched_jobs = semantic_match(
        state.get("resume_text", ""),
        state.get("job_listings", []),
        top_k=int(state.get("max_results") or 10),
        threshold=float(state.get("threshold") or 0.6),
    )
    if not matched_jobs:
        errors.append("No jobs met the configured relevance threshold.")
    return _merge_state(state, status="matching", resume_skills=resume_skills, matched_jobs=matched_jobs, errors=errors)


def generate_cover_letters_node(state: AgentState) -> dict[str, Any]:
    """Generate cover letters and skill gap metadata for matched jobs.

    Args:
        state: Current agent state.

    Returns:
        Updated state fields.
    """

    errors = list(state.get("errors", []))
    cover_letters: list[dict[str, Any]] = []
    has_groq_key = bool(os.getenv("GROQ_API_KEY"))

    for index, job in enumerate(state.get("matched_jobs", []), start=1):
        gap = analyze_gap(state.get("resume_skills", []), str(job.get("description") or ""))
        job_id = job.get("job_id") or f"job-{index}"
        try:
            if not has_groq_key:
                raise RuntimeError("GROQ_API_KEY is missing")
            prompt_text = cover_letter_prompt.format(
                job_title=job.get("job_title") or "the role",
                company=job.get("company") or "your company",
                resume_skills=", ".join(state.get("resume_skills", [])),
                job_description=job.get("description") or "",
                candidate_name=state.get("candidate_name") or "Candidate",
            )
            letter = _call_groq(prompt_text)
            generation_error = None
        except Exception as exc:
            logger.exception("Cover letter generation failed for %s", job.get("url"))
            generation_error = f"Groq generation failed: {exc}"
            letter = _fallback_cover_letter(job, state, gap)

        cover_record = {
            "job_id": job_id,
            "company": job.get("company"),
            "role": job.get("job_title"),
            "letter": letter,
            "matching_skills": gap["matching_skills"],
            "missing_skills": gap["missing_skills"],
            "match_percentage": gap["match_percentage"],
        }
        if generation_error:
            cover_record["generation_error"] = generation_error
        cover_letters.append(cover_record)
    return _merge_state(state, status="generating", cover_letters=cover_letters, errors=errors)


def export_output_node(state: AgentState) -> dict[str, Any]:
    """Export final application payload as JSON.

    Args:
        state: Current agent state.

    Returns:
        Updated state fields.
    """

    cover_by_id = {str(item.get("job_id")): item for item in state.get("cover_letters", [])}
    applications: list[dict[str, Any]] = []
    for index, job in enumerate(state.get("matched_jobs", []), start=1):
        job_id = str(job.get("job_id") or f"job-{index}")
        cover = cover_by_id.get(job_id, {})
        applications.append(
            {
                "job_id": job_id,
                "job_title": job.get("job_title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "url": job.get("url"),
                "source": job.get("source"),
                "relevance_score": job.get("relevance_score"),
                "matching_skills": cover.get("matching_skills", []),
                "missing_skills": cover.get("missing_skills", []),
                "match_percentage": cover.get("match_percentage", 0.0),
                "cover_letter": cover.get("letter", ""),
                "scraped_at": job.get("scraped_at") or datetime.now(timezone.utc).isoformat(),
            }
        )
    filepath = state.get("output_path") or "output/applications.json"
    save_to_json(applications, filepath)
    return _merge_state(state, status="exporting", output_json=applications, output_path=filepath)


def error_handler_node(state: AgentState) -> dict[str, Any]:
    """Log accumulated errors and mark the pipeline failed.

    Args:
        state: Current agent state.

    Returns:
        Updated state fields.
    """

    for error in state.get("errors", []):
        logger.error("Agent error: %s", error)
    return _merge_state(state, status="failed")
