"""Score RAG answer quality for observability only — no retrieval behavior change (v2)."""
from __future__ import annotations

from typing import Any


def score_rag_answer(
    *,
    query: str,
    answer: str,
    chunks: list[dict[str, Any]] | None = None,
) -> float:
    """
    Heuristic 0–1 quality score: chunk coverage + answer length sanity.
    Stored for admin dashboards; does not affect ranking.
    """
    if not (answer or "").strip():
        return 0.0
    chunk_list = chunks or []
    if not chunk_list:
        return 0.15
    scores = [float(c.get("score") or 0.0) for c in chunk_list if isinstance(c, dict)]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    length_factor = min(len(answer.strip()) / 400.0, 1.0)
    return round(min(1.0, 0.4 * avg_score + 0.3 * length_factor + 0.3), 4)
