"""Parse PDF and DOCX resumes into normalized text payloads."""

from pathlib import Path
import logging

from docx import Document
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


def _word_count(text: str) -> int:
    """Count words in text.

    Args:
        text: Text to count.

    Returns:
        Number of whitespace-delimited words.
    """

    return len(text.split())


def parse_pdf(filepath: str) -> dict[str, str | int]:
    """Parse a PDF resume file.

    Args:
        filepath: Path to a PDF resume.

    Returns:
        Dictionary containing raw_text and word_count.
    """

    path = Path(filepath)
    logger.info("Parsing PDF resume: %s", path)
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    raw_text = "\n".join(page.strip() for page in pages if page.strip())
    return {"raw_text": raw_text, "word_count": _word_count(raw_text)}


def parse_docx(filepath: str) -> dict[str, str | int]:
    """Parse a DOCX resume file.

    Args:
        filepath: Path to a DOCX resume.

    Returns:
        Dictionary containing raw_text and word_count.
    """

    path = Path(filepath)
    logger.info("Parsing DOCX resume: %s", path)
    document = Document(str(path))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    raw_text = "\n".join(paragraphs)
    return {"raw_text": raw_text, "word_count": _word_count(raw_text)}


def parse_resume(filepath: str) -> dict[str, str | int]:
    """Parse a supported resume file.

    Args:
        filepath: Path to a PDF or DOCX resume.

    Returns:
        Dictionary containing raw_text and word_count.

    Raises:
        ValueError: If the file extension is unsupported.
    """

    suffix = Path(filepath).suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(filepath)
    if suffix == ".docx":
        return parse_docx(filepath)
    raise ValueError(f"Unsupported resume format: {suffix}. Use .pdf or .docx.")

