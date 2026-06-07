"""Streamlit UI for the autonomous Job Application Agent."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


def _badge(label: str, color: str) -> str:
    """Render a small HTML badge.

    Args:
        label: Badge text.
        color: CSS color token.

    Returns:
        HTML badge string.
    """

    safe_label = str(label).replace("<", "&lt;").replace(">", "&gt;")
    return f"<span class='skill-badge {color}'>{safe_label}</span>"


def _save_upload(uploaded_file: Any) -> str:
    """Persist a Streamlit upload to disk.

    Args:
        uploaded_file: Streamlit UploadedFile object.

    Returns:
        Saved file path.
    """

    upload_dir = Path(".streamlit_uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / uploaded_file.name
    path.write_bytes(uploaded_file.getbuffer())
    return str(path)


def _render_css() -> None:
    """Apply custom dark UI styling.

    Args:
        None.

    Returns:
        None.
    """

    st.markdown(
        """
        <style>
        .stApp { background: #0f172a; color: #e5e7eb; }
        [data-testid="stSidebar"] { background: #111827; border-right: 1px solid #243047; }
        h1, h2, h3 { color: #f8fafc; letter-spacing: 0; }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] {
            background: #182235;
            border-radius: 8px;
            color: #d1d5db;
            padding: 10px 14px;
        }
        .stMetric {
            background: #111827;
            border: 1px solid #253149;
            border-radius: 8px;
            padding: 14px;
        }
        .skill-badge {
            display: inline-block;
            border-radius: 999px;
            padding: 4px 9px;
            margin: 3px;
            font-size: 12px;
            font-weight: 600;
        }
        .green { background: #064e3b; color: #a7f3d0; border: 1px solid #10b981; }
        .red { background: #4c0519; color: #fecdd3; border: 1px solid #fb7185; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_results(state: dict[str, Any]) -> None:
    """Render completed agent results.

    Args:
        state: Final agent state.

    Returns:
        None.
    """

    tabs = st.tabs(["📋 Matched Jobs", "✉️ Cover Letters", "🔍 Skill Gap Analysis", "📦 Export"])
    matched_jobs = state.get("matched_jobs", [])
    output_json = state.get("output_json", [])
    cover_letters = state.get("cover_letters", [])

    with tabs[0]:
        col1, col2, col3 = st.columns(3)
        avg_score = sum(float(job.get("relevance_score", 0.0)) for job in matched_jobs) / len(matched_jobs) if matched_jobs else 0.0
        col1.metric("Total Scraped", len(state.get("job_listings", [])))
        col2.metric("Total Matched", len(matched_jobs))
        col3.metric("Avg Relevance Score", f"{avg_score:.2f}")
        rows = [
            {
                "job_title": job.get("job_title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "source": job.get("source"),
                "relevance_score": job.get("relevance_score"),
                "url": job.get("url"),
            }
            for job in matched_jobs
        ]
        st.dataframe(
            rows,
            use_container_width=True,
            column_config={"url": st.column_config.LinkColumn("url")},
            hide_index=True,
        )

    with tabs[1]:
        for item in cover_letters:
            with st.expander(f"{item.get('company') or 'Unknown Company'} — {item.get('role') or 'Unknown Role'}"):
                st.metric("Skill Match", f"{float(item.get('match_percentage', 0.0)):.1f}%")
                st.markdown(" ".join(_badge(skill, "green") for skill in item.get("matching_skills", [])), unsafe_allow_html=True)
                st.markdown(" ".join(_badge(skill, "red") for skill in item.get("missing_skills", [])), unsafe_allow_html=True)
                if item.get("generation_error"):
                    st.warning("Groq generation failed, so a local fallback cover letter was created.")
                st.write(item.get("letter", ""))

    with tabs[2]:
        gap_rows = [
            {
                "company": item.get("company"),
                "role": item.get("role"),
                "match_%": item.get("match_percentage", 0.0),
                "matching_skills": ", ".join(item.get("matching_skills", [])),
                "missing_skills": ", ".join(item.get("missing_skills", [])),
            }
            for item in cover_letters
        ]
        if gap_rows:
            chart_df = pd.DataFrame(gap_rows).set_index("company")
            st.bar_chart(chart_df["match_%"])
        st.dataframe(gap_rows, use_container_width=True, hide_index=True)

    with tabs[3]:
        st.json(output_json[:2])
        json_data = json.dumps(output_json, indent=2)
        st.download_button(
            "Download JSON",
            data=json_data,
            file_name="applications.json",
            mime="application/json",
        )
        st.info(f"Saved on disk: {state.get('output_path', 'output/applications.json')}")

    if state.get("errors"):
        st.error("\n".join(str(error) for error in state["errors"]))


def main() -> None:
    """Run the Streamlit application.

    Args:
        None.

    Returns:
        None.
    """

    st.set_page_config(page_title="Job Application Agent", layout="wide", page_icon="🤖", initial_sidebar_state="expanded")
    _render_css()

    with st.sidebar:
        st.title("⚙️ Configuration")
        job_title = st.text_input("Job Title", value="AI Engineer")
        location = st.text_input("Location", value="Remote")
        candidate_name = st.text_input("Candidate Full Name", value="")
        max_results = st.slider("Max Results per source", min_value=5, max_value=50, value=20)
        threshold = st.slider("Relevance Threshold", min_value=0.0, max_value=1.0, value=0.6, step=0.05)
        uploaded_resume = st.file_uploader("Upload Resume", type=["pdf", "docx"])
        run_clicked = st.button("🚀 Run Agent", use_container_width=True)

    st.title("🤖 Job Application Agent")
    st.caption("Autonomous scraping, matching, cover letter generation, skill-gap analysis, and JSON export.")

    if run_clicked:
        if not uploaded_resume:
            st.error("Upload a PDF or DOCX resume before running the agent.")
            return
        if not candidate_name.strip():
            st.error("Enter the candidate full name before running the agent.")
            return

        progress = st.progress(0)
        with st.status("Running agent pipeline...", expanded=True) as status:
            try:
                status.write("Parsing resume and starting job search.")
                resume_path = _save_upload(uploaded_resume)
                progress.progress(15)
                from agent.graph import run_agent

                state = run_agent(resume_path, job_title, location, candidate_name, max_results, threshold)
                progress.progress(100)
                if state.get("status") == "failed":
                    status.update(label="Pipeline finished with errors.", state="error")
                else:
                    status.update(label="Pipeline completed.", state="complete")
                st.session_state["agent_state"] = state
            except Exception as exc:
                logger.exception("Agent execution failed")
                progress.progress(100)
                status.update(label="Pipeline failed.", state="error")
                st.error(f"Agent execution failed: {exc}")

    if "agent_state" in st.session_state:
        _render_results(st.session_state["agent_state"])


if __name__ == "__main__":
    main()
