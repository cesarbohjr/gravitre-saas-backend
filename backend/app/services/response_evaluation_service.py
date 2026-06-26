"""v7 unified response evaluation records from existing v2/v5 signals."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.services.rag_outcome_tracking import aggregate_chunk_outcome_summary
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

COMPOSITE_SCORE_WEIGHTS = {
    "rag_quality_score": 0.4,
    "user_feedback": 0.4,
    "chunk_reliability_avg": 0.2,
}


def compute_composite_score(signals: dict[str, Any]) -> float:
    """
    Explainable weighted composite; re-normalizes when signals are missing.
    Missing user_feedback is omitted — never treated as negative.
    """
    present: dict[str, float] = {}
    rag_quality = signals.get("rag_quality_score")
    if rag_quality is not None:
        present["rag_quality_score"] = max(0.0, min(1.0, float(rag_quality)))
    user_feedback = signals.get("user_feedback")
    if user_feedback in {"helpful", "not_helpful"}:
        present["user_feedback"] = 1.0 if user_feedback == "helpful" else 0.0
    chunk_avg = signals.get("chunk_reliability_avg")
    if chunk_avg is not None:
        present["chunk_reliability_avg"] = max(0.0, min(1.0, float(chunk_avg)))
    if not present:
        return 0.0
    total_weight = sum(COMPOSITE_SCORE_WEIGHTS[key] for key in present)
    weighted = sum(COMPOSITE_SCORE_WEIGHTS[key] * value for key, value in present.items())
    return round(weighted / total_weight, 4)


async def _load_feedback(org_id: str, message_id: str, client: Any) -> tuple[str | None, str | None]:
    fb = (
        client.table("message_feedback")
        .select("feedback, reason")
        .eq("org_id", org_id)
        .eq("message_id", message_id)
        .limit(1)
        .execute()
    )
    if fb.data:
        row = fb.data[0]
        return str(row.get("feedback") or ""), row.get("reason")
    pattern = (
        client.table("user_query_patterns")
        .select("feedback_helpful, rag_quality_score, response_time_ms, surface")
        .eq("org_id", org_id)
        .eq("message_id", message_id)
        .limit(1)
        .execute()
    )
    if pattern.data:
        row = pattern.data[0]
        helpful = row.get("feedback_helpful")
        if helpful is True:
            return "helpful", None
        if helpful is False:
            return "not_helpful", None
    return None, None


async def _load_rag_quality_score(org_id: str, message_id: str, client: Any) -> float | None:
    pattern = (
        client.table("user_query_patterns")
        .select("rag_quality_score")
        .eq("org_id", org_id)
        .eq("message_id", message_id)
        .limit(1)
        .execute()
    )
    if pattern.data and pattern.data[0].get("rag_quality_score") is not None:
        return float(pattern.data[0]["rag_quality_score"])
    return None


async def _load_surface(org_id: str, message_id: str, client: Any) -> str:
    pattern = (
        client.table("user_query_patterns")
        .select("surface")
        .eq("org_id", org_id)
        .eq("message_id", message_id)
        .limit(1)
        .execute()
    )
    if pattern.data and pattern.data[0].get("surface"):
        return str(pattern.data[0]["surface"])
    return "assistant"


async def consolidate_evaluation(
    settings: Any,
    org_id: str,
    message_id: str,
    *,
    client: Any | None = None,
) -> dict[str, Any] | None:
    """
    Join rag_quality_score, message_feedback, and rag_chunk_outcomes into one row.
    Returns None until user feedback exists (retry later via backfill).
    """
    db = client or get_supabase_client(settings)
    user_feedback, feedback_reason = await _load_feedback(org_id, message_id, db)
    if user_feedback not in {"helpful", "not_helpful"}:
        return None

    chunk_summary = await aggregate_chunk_outcome_summary(org_id, message_id, db)
    rag_quality_score = await _load_rag_quality_score(org_id, message_id, db)
    surface = await _load_surface(org_id, message_id, db)

    response_latency_ms = None
    pattern = (
        db.table("user_query_patterns")
        .select("response_time_ms")
        .eq("org_id", org_id)
        .eq("message_id", message_id)
        .limit(1)
        .execute()
    )
    if pattern.data and pattern.data[0].get("response_time_ms") is not None:
        response_latency_ms = int(pattern.data[0]["response_time_ms"])

    chunk_reliability_avg = None
    retrieval_latency_ms = None
    if chunk_summary:
        chunk_reliability_avg = chunk_summary.get("avg_reliability")
        retrieval_latency_ms = chunk_summary.get("retrieval_latency_ms")

    composite_score = compute_composite_score(
        {
            "rag_quality_score": rag_quality_score,
            "user_feedback": user_feedback,
            "chunk_reliability_avg": chunk_reliability_avg,
        }
    )
    row = {
        "id": str(uuid4()),
        "org_id": org_id,
        "message_id": message_id,
        "surface": surface,
        "rag_quality_score": rag_quality_score,
        "user_feedback": user_feedback,
        "feedback_reason": feedback_reason,
        "chunk_outcome_summary": chunk_summary,
        "retrieval_latency_ms": retrieval_latency_ms,
        "response_latency_ms": response_latency_ms,
        "composite_score": composite_score,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        db.table("response_evaluations").upsert(row, on_conflict="message_id").execute()
    except Exception as exc:  # noqa: BLE001
        logger.debug("response_evaluations upsert skipped message_id=%s error=%s", message_id, exc)
        return None
    return row


async def consolidate_recent(
    settings: Any,
    org_id: str,
    *,
    since_days: int = 1,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """Backfill evaluations for recent messages with feedback but no evaluation row."""
    db = client or get_supabase_client(settings)
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    feedback_rows = (
        db.table("message_feedback")
        .select("message_id")
        .eq("org_id", org_id)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )
    consolidated: list[dict[str, Any]] = []
    for row in feedback_rows:
        message_id = str(row.get("message_id") or "")
        if not message_id:
            continue
        existing = (
            db.table("response_evaluations")
            .select("id")
            .eq("org_id", org_id)
            .eq("message_id", message_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            continue
        evaluation = await consolidate_evaluation(settings, org_id, message_id, client=db)
        if evaluation:
            consolidated.append(evaluation)
    return consolidated
