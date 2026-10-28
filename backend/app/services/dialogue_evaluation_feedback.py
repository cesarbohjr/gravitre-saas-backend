"""Tenant-scoped, metrics-only dialogue feedback through the canonical LEARN stage.

No prompt, transcript, response, source record, error body, model judge or raw
provider identity is persisted/exported. Evaluation observations are never
business outcomes, tool permissions, memory facts or automatic prompt promotion.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.core.safe_dict import safe_normalize_stored_dict

TABLE = "intelligence_outcome_events"
EVENT = "dialogue_evaluated"
VERSION = "dialogue-metrics-v1"


def metrics_for_turn(request: Any, context: Any) -> dict[str, Any]:
    """Derive structural observations from actual kernel records, not model claims."""
    stage_rows = [r for r in context.stages if r.stage != "LEARN"]
    elapsed = sum(r.ms for r in stage_rows if isinstance(r.ms, (int, float)) and r.ms >= 0)
    return {
        "schema": 1, "evaluator_version": VERSION,
        "channel": "voice" if request.spoken_mode else "text",
        "stage_count": min(len(stage_rows), 20),
        "failed_stage_count": min(sum(r.ok is False for r in stage_rows), 20),
        "duration_ms": min(round(elapsed), 604800000),
        "evidence_kind": "runtime_structure", "quality_judged": False,
        "physical_voice_certified": False,
    }


def _read(client: Any, org_id: str, event_id: str) -> list:
    return (client.table(TABLE).select("id,org_id,outcome_event,metadata")
            .eq("org_id", org_id).eq("id", event_id).eq("outcome_event", EVENT).limit(1).execute().data or [])


def purge_feedback(client: Any, org_id: str, *, before: datetime | None = None) -> None:
    """Explicit opt-out erasure, or retention purge; never touches other outcomes."""
    query = client.table(TABLE).delete().eq("org_id", org_id).eq("outcome_event", EVENT)
    if before is not None:
        query = query.lt("created_at", before.isoformat())
    query.execute()
    verify = client.table(TABLE).select("id").eq("org_id", org_id).eq("outcome_event", EVENT)
    if before is not None:
        verify = verify.lt("created_at", before.isoformat())
    if verify.limit(1).execute().data:
        raise ValueError("evaluation_feedback_erasure_unverified")


async def record_turn_feedback(request: Any, context: Any, settings: Any) -> dict:
    """Read consent from authenticated tenant settings, then persist and read back.

    No request/model supplied permit is accepted. Speculation is deferred by
    run_learn before reaching this function. Failure does not change business ACT.
    """
    if request.client is None or not request.org_id or not request.user_id:
        return {"status": "disabled"}
    from app.core.io_pool import run_io
    from app.services.chat_dialogue_settings import load_chat_dialogue_settings
    try:
        config = await load_chat_dialogue_settings(request.org_id, settings, client=request.client)
        if config.get("evaluation_feedback_enabled") is not True:
            return {"status": "disabled"}
        days = config.get("evaluation_feedback_retention_days", 30)
        if type(days) is not int or not 1 <= days <= 90:
            return {"status": "invalid_retention"}
        now = datetime.now(timezone.utc)
        await run_io(lambda: purge_feedback(request.client, request.org_id, before=now-timedelta(days=days)))
        # Tenant and user are part of the deterministic receipt identity.
        event_id = str(uuid5(NAMESPACE_URL, repr((request.org_id, request.user_id, context.turn_id, VERSION))))
        metrics = metrics_for_turn(request, context)
        existing = await run_io(lambda: _read(request.client, request.org_id, event_id))
        if not existing:
            payload = {"id": event_id, "org_id": request.org_id, "outcome_event": EVENT,
                       "entity_type": "dialogue_turn", "entity_id": context.turn_id,
                       "metadata": metrics, "created_at": now.isoformat()}
            try:
                await run_io(lambda: request.client.table(TABLE).insert(payload).execute())
            except Exception:
                # A concurrent identical retry may have won. Readback decides.
                pass
        receipt = await run_io(lambda: _read(request.client, request.org_id, event_id))
        if len(receipt) != 1 or receipt[0].get("org_id") != request.org_id or receipt[0].get("outcome_event") != EVENT:
            return {"status": "unverified"}
        if safe_normalize_stored_dict(receipt[0].get("metadata")) != metrics:
            return {"status": "receipt_mismatch"}
        return {"status": "recorded", "receipt_id": event_id, "evaluator_version": VERSION}
    except Exception:
        return {"status": "feedback_failed"}


def feedback_summary(client: Any, org_id: str, *, retention_days: int = 30) -> dict:
    """Bounded tenant-only evidence for offline optimization review; no training export.

    Does not select examples, rewrite prompts, claim quality or automatically
    change the active version. Raw source rows never leave this function.
    """
    if not org_id or type(retention_days) is not int or not 1 <= retention_days <= 90:
        raise ValueError("invalid_feedback_scope")
    cutoff = (datetime.now(timezone.utc)-timedelta(days=retention_days)).isoformat()
    rows = (client.table(TABLE).select("org_id,outcome_event,metadata,created_at")
            .eq("org_id", org_id).eq("outcome_event", EVENT).gte("created_at", cutoff)
            .order("created_at", desc=True).limit(500).execute().data or [])
    counts = {"text": {"turns":0,"failed_stages":0}, "voice": {"turns":0,"failed_stages":0}}
    for row in rows:
        if row.get("org_id") != org_id or row.get("outcome_event") != EVENT:
            continue
        metric = safe_normalize_stored_dict(row.get("metadata"))
        channel = metric.get("channel")
        failed = metric.get("failed_stage_count")
        if metric.get("evaluator_version") == VERSION and isinstance(channel, str) and channel in counts and type(failed) is int and 0 <= failed <= 20:
            counts[channel]["turns"] += 1
            counts[channel]["failed_stages"] += failed
    return {"evaluator_version": VERSION, "channels": counts, "quality_judged":False,
            "automatic_promotion":False, "bounded_to_latest":500}
