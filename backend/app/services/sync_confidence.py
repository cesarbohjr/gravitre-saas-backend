"""Synchronous confidence estimate during response generation."""
from __future__ import annotations

from typing import Any

from app.services.rag_quality_scoring import score_rag_answer


def compute_sync_confidence(
    *,
    query: str,
    answer: str,
    chunks: list[dict[str, Any]] | None,
    validation_confidence: float | None = None,
    conflict_count: int = 0,
) -> dict[str, Any]:
    """
    Fast 0–1 confidence for live gating. Distinct from async response_evaluations.
    Returns score, band, and needs_clarification flag.
    """
    rag_score = score_rag_answer(query=query, answer=answer, chunks=chunks)
    blended = rag_score
    if validation_confidence is not None:
        blended = round(0.6 * rag_score + 0.4 * float(validation_confidence), 4)
    if conflict_count > 0:
        blended = round(max(0.0, blended - min(0.2, 0.08 * conflict_count)), 4)

    if blended >= 0.7:
        band = "high"
    elif blended >= 0.45:
        band = "medium"
    else:
        band = "low"

    return {
        "score": blended,
        "band": band,
        "needs_clarification": blended < 0.4,
        "rag_quality_score": rag_score,
    }
