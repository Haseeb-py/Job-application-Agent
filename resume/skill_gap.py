"""Skill extraction and gap analysis against job descriptions."""

import logging
import re

logger = logging.getLogger(__name__)

SKILL_TAXONOMY: tuple[str, ...] = (
    "Python", "LangChain", "LangGraph", "Docker", "SQL", "React", "FastAPI",
    "TensorFlow", "PyTorch", "FAISS", "Hugging Face", "Scikit-learn", "AWS",
    "GCP", "Azure", "Kubernetes", "Spark", "Kafka", "Redis", "MongoDB",
    "PostgreSQL", "REST API", "GraphQL", "TypeScript", "JavaScript", "Node.js",
    "Next.js", "Streamlit", "Groq", "OpenAI", "Anthropic", "RAG", "Vector DB",
    "Pinecone", "ChromaDB", "Weaviate", "Git", "CI/CD", "Airflow", "dbt",
    "Tableau", "Power BI", "NLP", "Computer Vision", "Transformers", "BERT",
    "GPT", "LLM", "Fine-tuning", "Prompt Engineering", "MLflow",
    "Weights & Biases", "Selenium", "BeautifulSoup", "Scrapy", "Pandas",
    "NumPy", "Matplotlib", "Seaborn", "Plotly", "Flask", "Django", "Linux",
    "Bash", "Terraform", "sentence-transformers", "PyPDF2", "Celery",
    "Java", "C++", "C#", "Go", "Rust", "Ruby", "PHP", "HTML", "CSS",
    "Tailwind CSS", "Bootstrap", "Vue", "Angular", "Express", "Django REST",
    "MySQL", "SQLite", "Oracle", "Snowflake", "BigQuery", "Databricks",
    "Elasticsearch", "RabbitMQ", "Jenkins", "GitHub Actions", "GitLab CI",
    "Ansible", "Prometheus", "Grafana", "ONNX", "spaCy", "NLTK", "XGBoost",
    "LightGBM", "Keras", "Jupyter", "REST", "Microservices", "OAuth",
    "LangSmith", "LlamaIndex", "Qdrant",
)


def _contains_skill(text: str, skill: str) -> bool:
    """Check whether text contains a skill as a case-insensitive exact term.

    Args:
        text: Text to search.
        skill: Skill term from the taxonomy.

    Returns:
        True when the skill appears as a standalone term.
    """

    escaped = re.escape(skill)
    pattern = rf"(?<![A-Za-z0-9+#.]){escaped}(?![A-Za-z0-9+#.])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def extract_skills(resume_text: str) -> list[str]:
    """Extract skills from text using a fixed technology taxonomy.

    Args:
        resume_text: Resume or job description text.

    Returns:
        Sorted list of matched skill strings.
    """

    if not resume_text:
        return []
    matches = [skill for skill in SKILL_TAXONOMY if _contains_skill(resume_text, skill)]
    logger.info("Extracted %d skills", len(matches))
    return sorted(dict.fromkeys(matches), key=str.lower)


def analyze_gap(resume_skills: list[str], job_description: str) -> dict[str, list[str] | float]:
    """Analyze skill overlap between a resume and job description.

    Args:
        resume_skills: Skills extracted from the candidate resume.
        job_description: Full job description text.

    Returns:
        Dictionary with matching_skills, missing_skills, and match_percentage.
    """

    job_skills = extract_skills(job_description)
    resume_set = {skill.lower(): skill for skill in resume_skills}
    matching = [skill for skill in job_skills if skill.lower() in resume_set]
    missing = [skill for skill in job_skills if skill.lower() not in resume_set]
    percentage = (len(matching) / len(job_skills) * 100.0) if job_skills else 0.0
    return {
        "matching_skills": matching,
        "missing_skills": missing,
        "match_percentage": round(percentage, 2),
    }

