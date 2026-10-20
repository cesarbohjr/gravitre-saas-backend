"""Finished runs reach the learners through the domain-event outbox.

The ``workflow_runs`` trigger writes ``execution.outcome_finalized`` for every
terminal transition (migration 20261012024141). This handler, run by the relay,
takes one such event and, for that run only:

1. Work object and goal: when the run names a work object (``parameters.work_object_id``)
   in the same org and that object has no event for this run yet, the outcome is
   recorded on it through ``record_execution_work_object``. Goal completion is
   derived from linked work-object status (``goal_link_progress``), so it moves
   with it; the handler only reads it back. No link means nothing is created.
2. Prediction ledger: open (``pending``) predictions whose subject is this run or
   its workflow, made before the run finished and inside their horizon, are
   labelled through ``record_prediction_outcome`` when the prediction names a
   success or failure and the run completed or failed. Predictions about other
   subjects (a customer's churn) are not labelled from a run finishing: that is
   not evidence about them, and the labelling job resolves them from their own
   source of record. Needs ML_PREDICTION_OUTCOMES_ENABLED (migration 20261012060000).
3. Recommendation learning: verified Play results already attributed to the run
   are fed to ``RecommendationQualityEngine.learn_from_run_outcome``.

Idempotent per event: each write is keyed so a replay finds it and records
nothing. Missing rows or links are skips; database errors propagate so the relay
retries with backoff. Off unless OUTCOME_LEARNING_HANDLER_ENABLED is true.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.domain_events import (
    EVENT_EXECUTION_OUTCOME_FINALIZED,
    handlers_for,
    register_domain_event_handler,
)

logger = get_logger(__name__)

HANDLER_NAME = "outcome_learning.record_run_outcome"

PREDICTION_SUBJECT_RUN = "workflow_run"
PREDICTION_SUBJECT_WORKFLOW = "workflow"
_SUCCESS_LABELS = frozenset({"success", "succeeded", "completed", "complete", "pass", "passed"})
_FAILURE_LABELS = frozenset({"failure", "failed", "fail", "error"})
_OBSERVED_BY_STATUS = {"completed": "success", "failed": "failure"}
_LEDGER_LABEL_EVENTS = ("prediction_validated", "prediction_missed")
_MAX_PREDICTIONS_PER_SUBJECT = 50
_ID_NAMESPACE = uuid.UUID("b0b8f0a4-0f55-4a43-9a8e-5d3e2f6c7a91")


def handler_enabled(settings: Any) -> bool:
    return getattr(settings, "outcome_learning_handler_enabled", False) is True


def learning_delivery_status(client: Any, settings: Any, *, org_id: str) -> dict[str, Any]:
    """Expose effective runtime gates and this tenant's undelivered outcomes.

    Delivery is not model improvement: a handler may legitimately skip a run
    without verified business results. Do not label queued rows as learned.
    Payloads and raw error messages are intentionally excluded.
    """
    from app.services.domain_events import EVENT_EXECUTION_OUTCOME_FINALIZED

    if not org_id:
        raise ValueError("Organization context required")
    relay_enabled = getattr(settings, "domain_event_relay_enabled", False) is True
    enabled = handler_enabled(settings)
    registered = any(r.name == HANDLER_NAME for r in handlers_for(EVENT_EXECUTION_OUTCOME_FINALIZED))
    response = (
        client.table("domain_event_outbox")
        .select("event_id,aggregate_id,status,attempts,created_at", count="exact")
        .eq("org_id", org_id)
        .eq("event_type", EVENT_EXECUTION_OUTCOME_FINALIZED)
        .in_("status", ["pending", "processing", "retrying", "dead"])
        .order("created_at")
        .limit(20)
        .execute()
    )
    rows = response.data or []
    blockers = []
    if not relay_enabled:
        blockers.append("relay_disabled")
    if not enabled:
        blockers.append("outcome_handler_disabled")
    elif not registered:
        blockers.append("outcome_handler_not_registered")
    return {
        "status": "blocked" if blockers else "queued" if rows else "idle",
        "relay_enabled": relay_enabled,
        "handler_enabled": enabled,
        "handler_registered": registered,
        "blockers": blockers,
        "undelivered_count": response.count,
        "events": rows,
        "delivery_is_not_verified_learning": True,
    }


def _parse(ts: Any) -> datetime | None:
    if not ts:
        return None
    try:
        out = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    return out if out.tzinfo else out.replace(tzinfo=UTC)


def _load_run(client: Any, org_id: str, run_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("workflow_runs")
        .select("id, org_id, workflow_id, status, completed_at, error_message, parameters")
        .eq("org_id", org_id)
        .eq("id", run_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows and isinstance(rows[0], dict) else None


def _record_work_object(
    client: Any, *, org_id: str, run: dict[str, Any], status: str, params: dict[str, Any]
) -> dict[str, Any]:
    work_object_id = str(params.get("work_object_id") or "").strip()
    if not work_object_id:
        return {"skipped": "no_work_object_link"}
    rows = (
        client.table("work_objects")
        .select("id, goal_id, department")
        .eq("org_id", org_id)
        .eq("id", work_object_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        # Wrong org or deleted: never write across orgs, never create one here.
        return {"skipped": "work_object_not_found"}
    work_object = rows[0]
    out: dict[str, Any] = {
        "work_object_id": work_object_id,
        "department": work_object.get("department"),
        "goal_id": work_object.get("goal_id"),
    }
    already = (
        client.table("work_object_events")
        .select("id")
        .eq("org_id", org_id)
        .eq("work_object_id", work_object_id)
        .eq("run_id", str(run["id"]))
        .limit(1)
        .execute()
        .data
        or []
    )
    if already:
        out["recorded"] = False
        out["already_recorded"] = True
    else:
        from app.services.work_object_service import record_execution_work_object

        verified = params.get("verified_output") if isinstance(params.get("verified_output"), dict) else None
        record_execution_work_object(
            client,
            org_id=org_id,
            run_id=str(run["id"]),
            terminal_status=status,
            metadata=params,
            verified_output=verified,
            workflow_id=str(run.get("workflow_id") or "") or None,
            error_summary=run.get("error_message"),
        )
        out["recorded"] = True
    if work_object.get("goal_id"):
        from app.services.goal_records import goal_link_progress

        out["goal_progress"] = goal_link_progress(client, org_id, str(work_object["goal_id"]))
    return out


def _predicted_class(label: Any) -> str | None:
    text = str(label or "").strip().lower()
    if text in _SUCCESS_LABELS:
        return "success"
    if text in _FAILURE_LABELS:
        return "failure"
    return None


async def _label_predictions(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    run: dict[str, Any],
    status: str,
    completed_at: datetime | None,
    source_event_id: str,
) -> dict[str, Any]:
    from app.ml.prediction_outcomes import outcomes_enabled

    if not outcomes_enabled(settings):
        return {"skipped": "prediction_outcomes_disabled"}
    observed = _OBSERVED_BY_STATUS.get(status)
    counts = {"labelled": 0, "already_labelled": 0, "no_evidence": 0, "out_of_window": 0}
    subjects = [(PREDICTION_SUBJECT_RUN, str(run["id"]))]
    if run.get("workflow_id"):
        subjects.append((PREDICTION_SUBJECT_WORKFLOW, str(run["workflow_id"])))
    from app.services.outcome_learning_service import OutcomeLearningService

    service = OutcomeLearningService(settings)
    for subject_type, subject_id in subjects:
        pending = (
            client.table("model_predictions")
            .select("id, model_id, predicted_label, predicted_score, horizon_days, created_at")
            .eq("org_id", org_id)
            .eq("label_status", "pending")
            .eq("subject_type", subject_type)
            .eq("subject_id", subject_id)
            .order("created_at")
            .limit(_MAX_PREDICTIONS_PER_SUBJECT)
            .execute()
            .data
            or []
        )
        for pred in pending:
            predicted = _predicted_class(pred.get("predicted_label"))
            if observed is None or predicted is None:
                counts["no_evidence"] += 1
                continue
            made = _parse(pred.get("created_at"))
            horizon = int(pred.get("horizon_days") or 0)
            if completed_at is None or made is None or not (
                made <= completed_at <= made + timedelta(days=horizon)
            ):
                counts["out_of_window"] += 1
                continue
            pid = str(pred["id"])
            labelled = (
                client.table("intelligence_outcome_events")
                .select("id")
                .eq("org_id", org_id)
                .eq("prediction_id", pid)
                .in_("outcome_event", list(_LEDGER_LABEL_EVENTS))
                .limit(1)
                .execute()
                .data
                or []
            )
            if labelled:
                counts["already_labelled"] += 1
                continue
            happened = predicted == observed
            score = pred.get("predicted_score")
            await service.record_prediction_outcome(
                org_id,
                pid,
                str(pred.get("model_id") or ""),
                float(score) if score is not None else 1.0,
                1.0 if happened else 0.0,
                "prediction_validated" if happened else "prediction_missed",
                metadata={
                    "workflow_run_id": str(run["id"]),
                    "observed": observed,
                    "source_event_id": source_event_id,
                },
                outcome_id=str(uuid.uuid5(_ID_NAMESPACE, f"prediction:{pid}")),
                client=client,
                strict=True,
            )
            counts["labelled"] += 1
    return counts


async def _record_run_outcome(
    client: Any, settings: Settings, event: dict[str, Any]
) -> dict[str, Any]:
    org_id = str(event.get("org_id") or "")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    run_id = str(payload.get("run_id") or event.get("aggregate_id") or "")
    status = str(payload.get("status") or "")
    if not org_id or not run_id or not status:
        return {"skipped": "malformed_event"}
    run = _load_run(client, org_id, run_id)
    if run is None:
        return {"skipped": "run_not_found"}
    params = run.get("parameters") if isinstance(run.get("parameters"), dict) else {}
    completed_at = _parse(payload.get("completed_at") or run.get("completed_at"))
    result: dict[str, Any] = {"run_id": run_id, "status": status}

    result["work_object"] = _record_work_object(client, org_id=org_id, run=run, status=status, params=params)
    result["predictions"] = await _label_predictions(
        client,
        settings,
        org_id=org_id,
        run=run,
        status=status,
        completed_at=completed_at,
        source_event_id=str(event.get("event_id") or ""),
    )
    play = params.get("play") if isinstance(params.get("play"), dict) else {}
    from app.services.recommendation_quality_engine import RecommendationQualityEngine

    result["recommendation_learning"] = await RecommendationQualityEngine(settings).learn_from_run_outcome(
        client,
        org_id=org_id,
        run_id=run_id,
        play_key=str(play.get("key") or "").strip() or None,
        department=result["work_object"].get("department"),
    )
    logger.info(
        "outcome_learning_recorded event_id=%s org_id=%s run_id=%s status=%s work_object=%s predictions=%s recommendation_learning=%s",
        event.get("event_id"),
        org_id,
        run_id,
        status,
        result["work_object"].get("recorded", result["work_object"].get("skipped")),
        result["predictions"],
        result["recommendation_learning"],
    )
    return result


def handle_execution_outcome_finalized(
    client: Any, event: dict[str, Any], settings: Settings | None = None
) -> dict[str, Any]:
    settings = settings or get_settings()
    if not handler_enabled(settings):
        return {"skipped": "disabled"}
    # The relay runs handlers in a worker thread with no running event loop.
    return asyncio.run(_record_run_outcome(client, settings, event))


def register_outcome_learning_handlers(settings: Settings | None = None) -> bool:
    """Register only when the flag is on, so events are not marked delivered while it is off."""
    settings = settings or get_settings()
    if not handler_enabled(settings):
        return False
    if any(r.name == HANDLER_NAME for r in handlers_for(EVENT_EXECUTION_OUTCOME_FINALIZED)):
        return True
    register_domain_event_handler(
        EVENT_EXECUTION_OUTCOME_FINALIZED,
        HANDLER_NAME,
        lambda client, event: handle_execution_outcome_finalized(client, event),
    )
    return True
