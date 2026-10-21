"""v5 RAG chunk outcome tracking linked to assistant message responses."""
from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


async def record_retrieval_outcomes(
    settings: Any,
    *,
    org_id: str,
    message_id: str,
    rows: list[dict[str, Any]],
    retrieval_latency_ms: int | None = None,
    reliability_scores: dict[str, float] | None = None,
    client: Any | None = None,
) -> None:
    """Persist retrieved chunks for later feedback-driven reliability scoring."""
    if not message_id or not rows:
        return
    db = client or get_supabase_client(settings)
    payload = []
    for rank, row in enumerate(rows, start=1):
        chunk_id = str(row.get("id") or row.get("chunk_id") or "").strip() or None
        doc_id = str(row.get("document_id") or row.get("source_document_id") or "").strip() or None
        payload.append(
            {
                "id": str(uuid4()),
                "org_id": org_id,
                "message_id": message_id,
                "chunk_id": chunk_id,
                "source_document_id": doc_id,
                "rerank_score": float(row.get("rerank_score") or row.get("score") or 0.0),
                "rank_position": rank,
                "outcome_helpful": None,
                "retrieval_latency_ms": retrieval_latency_ms,
            }
        )
    # Freeze actual pre-feedback features at the existing observation boundary.
    # Historical rows are never backfilled from today's reliability or dates.
    if reliability_scores:
        try:
            from app.ml.training_consent import training_is_approved
            if (await training_is_approved(org_id,"federated_learning",settings)
                    and await training_is_approved(org_id,"retrieval_ranker",settings)):
                from app.ml.federated_learning import verified_privacy_profile
                from app.ml.federated_adoption import artifact_permission
                from types import SimpleNamespace
                _,audit = await asyncio.to_thread(verified_privacy_profile,settings)
                if not await artifact_permission(org_id,SimpleNamespace(federation={"audit_digest":audit}),settings):
                    raise ValueError("Current audited-program permission required")
                ids = sorted({row["source_document_id"] for row in payload if row["source_document_id"]})
                docs = await asyncio.to_thread(lambda: db.table("rag_documents").select("id,updated_at")
                    .eq("org_id",org_id).in_("id",ids).execute().data or []) if ids else []
                dates = {row["id"]:row.get("updated_at") for row in docs}
                observed = datetime.now(timezone.utc)
                for row in payload:
                    reliability = reliability_scores.get(row["source_document_id"])
                    try:
                        updated = datetime.fromisoformat(str(dates.get(row["source_document_id"])).replace("Z","+00:00"))
                    except ValueError:
                        continue
                    if updated.tzinfo is None or updated > observed or type(reliability) not in {int,float} or not math.isfinite(reliability):
                        continue
                    features = {"rerank_score":row["rerank_score"],"rank_position":row["rank_position"],
                                "source_reliability_score":reliability,"source_document_age_days":(observed-updated).total_seconds()/86400}
                    if not all(math.isfinite(value) for value in features.values()):
                        continue
                    row.update(ranker_features=features,ranker_features_observed_at=observed.isoformat(),recorded_at=observed.isoformat())
                    break  # One proxy label per assistant message, not per chunk.
        except Exception:
            logger.debug("federated_observation_snapshot_unavailable org_id=%s",org_id)
    try:
        db.table("rag_chunk_outcomes").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.debug("rag_chunk_outcomes insert skipped message_id=%s error=%s", message_id, exc)


async def apply_message_feedback(
    settings: Any,
    *,
    org_id: str,
    message_id: str,
    helpful: bool,
    reason: str | None = None,
    corrected_answer: str | None = None,
    client: Any | None = None,
) -> None:
    """Record user feedback and propagate to chunk outcomes."""
    db = client or get_supabase_client(settings)
    feedback_value = "helpful" if helpful else "not_helpful"
    row: dict[str, Any] = {
        "org_id": org_id,
        "message_id": message_id,
        "feedback": feedback_value,
        "reason": reason,
    }
    if corrected_answer:
        row["corrected_answer"] = corrected_answer[:4000]
    try:
        db.table("message_feedback").upsert(row, on_conflict="message_id").execute()
    except Exception as exc:  # noqa: BLE001
        logger.debug("message_feedback upsert skipped message_id=%s error=%s", message_id, exc)
        return
    try:
        db.table("rag_chunk_outcomes").update({"outcome_helpful": helpful}).eq(
            "org_id", org_id
        ).eq("message_id", message_id).execute()
        from app.ml.federated_adoption import schedule_feedback_reconciliation
        schedule_feedback_reconciliation(org_id,settings,db)
    except Exception as exc:  # noqa: BLE001
        logger.debug("rag_chunk_outcomes feedback update skipped message_id=%s error=%s", message_id, exc)


async def aggregate_chunk_outcome_summary(
    org_id: str,
    message_id: str,
    client: Any,
) -> dict[str, Any] | None:
    result = (
        client.table("rag_chunk_outcomes")
        .select("source_document_id, rerank_score, outcome_helpful, retrieval_latency_ms")
        .eq("org_id", org_id)
        .eq("message_id", message_id)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return None
    doc_ids = {str(row.get("source_document_id") or "") for row in rows if row.get("source_document_id")}
    reliabilities: list[float] = []
    for doc_id in doc_ids:
        doc_rows = [row for row in rows if str(row.get("source_document_id") or "") == doc_id]
        outcomes = [bool(row.get("outcome_helpful")) for row in doc_rows if row.get("outcome_helpful") is not None]
        if outcomes:
            reliabilities.append(sum(1 for v in outcomes if v) / len(outcomes))
    retrieval_latency = next(
        (row.get("retrieval_latency_ms") for row in rows if row.get("retrieval_latency_ms") is not None),
        None,
    )
    return {
        "chunks_used": len(rows),
        "avg_reliability": round(sum(reliabilities) / len(reliabilities), 4) if reliabilities else None,
        "flagged_stale_sources": [],
        "retrieval_latency_ms": retrieval_latency,
    }
