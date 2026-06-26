"""v5 source reliability scoring from rag_chunk_outcomes."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

RELIABILITY_WEIGHT = 0.15
RAG_RERANKING_ACTIVATION_MIN_SCORED_SOURCES = 3
MIN_OUTCOMES_FOR_SCORING = 10
MIN_LEARNED_WEIGHT = 0.05
MAX_LEARNED_WEIGHT = 0.35


def clip_reliability_weight(weight: float) -> float:
    """Bound learned or hand-picked reliability coefficients."""
    return max(MIN_LEARNED_WEIGHT, min(MAX_LEARNED_WEIGHT, float(weight)))


def compute_source_reliability(helpful_count: int, total_count: int) -> float | None:
    if total_count < MIN_OUTCOMES_FOR_SCORING:
        return None
    if total_count <= 0:
        return None
    return helpful_count / total_count


async def fetch_source_reliability_scores(org_id: str, client: Any) -> dict[str, float]:
    """Aggregate helpful/total per source_document_id from scored chunk outcomes."""
    result = (
        client.table("rag_chunk_outcomes")
        .select("source_document_id, outcome_helpful")
        .eq("org_id", org_id)
        .not_.is_("outcome_helpful", "null")
        .execute()
    )
    totals: dict[str, list[bool]] = {}
    for row in result.data or []:
        doc_id = str(row.get("source_document_id") or "").strip()
        if not doc_id:
            continue
        totals.setdefault(doc_id, []).append(bool(row.get("outcome_helpful")))
    scores: dict[str, float] = {}
    for doc_id, outcomes in totals.items():
        reliability = compute_source_reliability(sum(1 for v in outcomes if v), len(outcomes))
        if reliability is not None:
            scores[doc_id] = reliability
    return scores


def apply_reliability_adjustment(
    rows: list[dict[str, Any]],
    reliability_scores: dict[str, float],
    weight: float,
) -> list[dict[str, Any]]:
    """
    v5 bounded additive adjustment: final_score = rerank_score + weight * reliability.
    Skipped until enough sources have reliability scores.
    """
    scored_sources = len(reliability_scores)
    if scored_sources < RAG_RERANKING_ACTIVATION_MIN_SCORED_SOURCES:
        return rows

    bounded_weight = clip_reliability_weight(weight)
    adjusted: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        rerank_score = float(item.get("score") or 0.0)
        item["rerank_score"] = rerank_score
        doc_id = str(item.get("document_id") or item.get("source_document_id") or "").strip()
        reliability = reliability_scores.get(doc_id)
        if reliability is None:
            item["final_score"] = rerank_score
        else:
            item["final_score"] = rerank_score + bounded_weight * reliability
            item["score"] = item["final_score"]
        adjusted.append(item)
    adjusted.sort(key=lambda item: float(item.get("final_score") or item.get("score") or 0.0), reverse=True)
    return adjusted
