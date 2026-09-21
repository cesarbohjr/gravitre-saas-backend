"""Closed outcome loop helpers for CognitiveTurnKernel PLAN bias + LEARN."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.outcome_learning_service import (
    BUSINESS_IMPACT_EVENTS,
    POSITIVE_EVENTS,
    TOOL_SUCCESS_EVENTS,
    classify_outcome_layer,
)

logger = get_logger(__name__)


def bias_from_outcomes(
    client: Any,
    org_id: str,
    query: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Query recent intelligence_outcome_events for the org and return PLAN-injection notes.

    Always filters by ``org_id``. Best-effort when the table is missing.
    """
    _ = settings or get_settings()
    bias_notes: list[str] = []
    weight_delta = 0.0
    if not org_id or client is None:
        return {"bias_notes": bias_notes, "weight_delta": weight_delta}

    try:
        rows = (
            client.table("intelligence_outcome_events")
            .select("outcome_event, entity_type, entity_id, confidence_score, recommendation_id, created_at")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(25)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_outcome_bias_query_skipped error=%s", exc)
        return {"bias_notes": bias_notes, "weight_delta": weight_delta}

    needle = (query or "").strip().lower()
    positive = 0
    negative = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        event = str(row.get("outcome_event") or "")
        if event in TOOL_SUCCESS_EVENTS:
            continue
        layer = classify_outcome_layer(event)
        if layer not in {"business_outcomes", "decisions"}:
            continue
        entity = str(row.get("entity_id") or row.get("recommendation_id") or "")
        note = f"Prior {layer} {event}" + (f" on {entity[:48]}" if entity else "")
        if not needle or needle in note.lower() or needle in entity.lower():
            bias_notes.append(note)
        if event in POSITIVE_EVENTS or event in {"business_metric_improved"}:
            positive += 1
        elif event in BUSINESS_IMPACT_EVENTS or event in {
            "recommendation_rejected",
            "approval_denied",
            "user_feedback_negative",
        }:
            negative += 1

    if not bias_notes and any(
        classify_outcome_layer(str(row.get("outcome_event") or "")) in {"business_outcomes", "decisions"}
        for row in rows
        if isinstance(row, dict)
    ):
        bias_notes.append(
            f"Org has recent measured outcomes "
            f"({positive} positive-leaning, {negative} negative-leaning)."
        )

    if positive or negative:
        weight_delta = round((positive - negative) / max(positive + negative, 1) * 0.1, 4)

    return {"bias_notes": bias_notes[:10], "weight_delta": weight_delta}


async def record_closed_loop(
    *,
    org_id: str,
    recommendation_id: str,
    outcome_event: str,
    settings: Settings | None = None,
    department: str | None = None,
    task_type: str | None = None,
    model_name: str | None = None,
    confidence_score: float | None = None,
    before_value: float | None = None,
    after_value: float | None = None,
    measured_at: str | None = None,
    strategy_key: str | None = None,
    domain_context: dict[str, Any] | None = None,
    retrieval_effectiveness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap OutcomeLearningService.record_recommendation_outcome (best-effort)."""
    active = settings or get_settings()
    try:
        from app.services.outcome_learning_service import get_outcome_learning_service

        service = get_outcome_learning_service(active)
        await service.record_recommendation_outcome(
            org_id,
            recommendation_id,
            outcome_event,
            department=department,
            task_type=task_type,
            model_name=model_name,
            confidence_score=confidence_score,
            before_value=before_value,
            after_value=after_value,
            measured_at=measured_at,
            strategy_key=strategy_key,
            domain_context=domain_context,
            retrieval_effectiveness=retrieval_effectiveness,
        )
        return {"ok": True, "recommendation_id": recommendation_id, "outcome_event": outcome_event}
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_outcome_record_skipped error=%s", exc)
        return {"ok": False, "error": str(exc)[:200]}
