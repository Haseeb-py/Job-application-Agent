"""Semantic resume-to-job matching with sentence-transformers and FAISS."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
model = SentenceTransformer(MODEL_NAME)
_faiss_index: faiss.IndexFlatL2 | None = None
_indexed_signature: str | None = None
_indexed_jobs: list[dict[str, Any]] = []


def _signature(job_listings: list[dict[str, Any]]) -> str:
    """Create a stable signature for the current job descriptions.

    Args:
        job_listings: Job dictionaries to index.

    Returns:
        SHA-256 signature string.
    """

    payload = "\n".join(str(job.get("url") or "") + "::" + str(job.get("description") or "") for job in job_listings)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """Normalize embedding vectors for stable FAISS distance behavior.

    Args:
        embeddings: Two-dimensional embedding matrix.

    Returns:
        Float32 normalized embedding matrix.
    """

    array = np.asarray(embeddings, dtype="float32")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return array / norms


def semantic_match(
    resume_text: str,
    job_listings: list[dict[str, Any]],
    top_k: int = 10,
    threshold: float = 0.6,
) -> list[dict[str, Any]]:
    """Match a resume against job descriptions using FAISS similarity search.

    Args:
        resume_text: Raw resume text.
        job_listings: Jobs containing description fields.
        top_k: Maximum number of matched jobs to return.
        threshold: Minimum normalized relevance score from 0.0 to 1.0.

    Returns:
        Top matched job dictionaries with relevance_score added.
    """

    global _faiss_index, _indexed_signature, _indexed_jobs

    if not job_listings:
        logger.info("No job listings supplied for semantic matching")
        return []

    searchable_jobs = [job for job in job_listings if str(job.get("description") or "").strip()]
    if not searchable_jobs:
        logger.info("No job descriptions available for semantic matching")
        return []

    current_signature = _signature(searchable_jobs)
    if _faiss_index is None or _indexed_signature != current_signature:
        descriptions = [str(job.get("description") or "") for job in searchable_jobs]
        job_embeddings = _normalize_embeddings(model.encode(descriptions, convert_to_numpy=True, show_progress_bar=False))
        _faiss_index = faiss.IndexFlatL2(job_embeddings.shape[1])
        _faiss_index.add(job_embeddings)
        _indexed_signature = current_signature
        _indexed_jobs = searchable_jobs
        logger.info("Built FAISS index for %d jobs", len(searchable_jobs))

    resume_embedding = _normalize_embeddings(model.encode([resume_text], convert_to_numpy=True, show_progress_bar=False))
    k = min(max(top_k, 1), len(_indexed_jobs))
    distances, indices = _faiss_index.search(resume_embedding, k)

    matches: list[dict[str, Any]] = []
    for distance, index in zip(distances[0], indices[0]):
        if index < 0:
            continue
        similarity = max(0.0, min(1.0, 1.0 - (float(distance) / 4.0)))
        if similarity >= threshold:
            job = dict(_indexed_jobs[int(index)])
            job["relevance_score"] = round(similarity, 4)
            matches.append(job)

    return sorted(matches, key=lambda item: item.get("relevance_score", 0.0), reverse=True)[:top_k]

