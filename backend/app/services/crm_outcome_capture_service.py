"""Item 4 / Phase 5 — capture CRM outcome labels for learning.

Write path only when a connector/sync emits a real event. Never invent labels.
On successful insert, mirror won/lost into intelligence_outcome_events.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

CRM_OUTCOME_TYPES = frozenset({"contacted", "replied", "booked", "won", "lost"})

_CRM_TO_LEARNING_EVENT = {
    "won": "crm_won",
    "lost": "crm_lost",
    "contacted": "crm_contacted",
    "replied": "crm_replied",
    "booked": "crm_booked",
}


def ingest_crm_recommendation_outcome(
    client: Any,
    *,
    org_id: str,
    outcome_type: str,
    connector_type: str | None = None,
    external_record_id: str | None = None,
    recommendation_id: str | None = None,
    icp_score: float | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Persist one labeled CRM outcome. Raises ValueError on invalid type.

    Soft-dedupes on (org_id, connector_type, external_record_id, outcome_type) when
    external_record_id is present — select-before-insert, no schema change.
    """
    outcome = str(outcome_type or "").strip().lower()
    if outcome not in CRM_OUTCOME_TYPES:
        raise ValueError(f"Invalid CRM outcome_type: {outcome_type}")

    ctype = (connector_type or "").strip().lower() or None
    ext_id = (external_record_id or "").strip() or None

    if ext_id and ctype:
        try:
            existing = (
                client.table("crm_recommendation_outcomes")
                .select("id")
                .eq("org_id", org_id)
                .eq("connector_type", ctype)
                .eq("external_record_id", ext_id)
                .eq("outcome_type", outcome)
                .limit(1)
                .execute()
            )
            rows = getattr(existing, "data", None)
            if isinstance(rows, list) and rows:
                return {
                    "stored": False,
                    "deduped": True,
                    "id": str(rows[0]["id"]),
                    "outcomeType": outcome,
                }
        except Exception as exc:  # noqa: BLE001
            logger.debug("crm_outcome_dedupe_lookup_skipped err=%s", exc)

    row = {
        "id": str(uuid4()),
        "org_id": org_id,
        "outcome_type": outcome,
        "connector_type": ctype,
        "external_record_id": ext_id,
        "recommendation_id": (recommendation_id or "").strip() or None,
        "icp_score": icp_score,
        "metadata": metadata or {},
        "occurred_at": occurred_at or datetime.now(timezone.utc).isoformat(),
    }
    try:
        client.table("crm_recommendation_outcomes").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("crm_outcome_ingest_failed org_id=%s err=%s", org_id, exc)
        raise

    _mirror_to_intelligence_outcome_events(
        client,
        org_id=org_id,
        outcome_type=outcome,
        crm_row_id=row["id"],
        external_record_id=ext_id,
        recommendation_id=row.get("recommendation_id"),
        connector_type=ctype,
        metadata=metadata or {},
        occurred_at=row["occurred_at"],
    )

    return {"stored": True, "deduped": False, "id": row["id"], "outcomeType": outcome}


def _mirror_to_intelligence_outcome_events(
    client: Any,
    *,
    org_id: str,
    outcome_type: str,
    crm_row_id: str,
    external_record_id: str | None,
    recommendation_id: str | None,
    connector_type: str | None,
    metadata: dict[str, Any],
    occurred_at: str,
) -> None:
    """Phase 5.1 — sync bridge into intelligence_outcome_events (no event-loop required)."""
    learning_event = _CRM_TO_LEARNING_EVENT.get(outcome_type)
    if not learning_event:
        return
    entity_id = recommendation_id or external_record_id or crm_row_id
    payload = {
        "id": str(uuid4()),
        "org_id": org_id,
        "outcome_event": learning_event,
        "entity_type": "recommendation" if recommendation_id else "crm_deal",
        "entity_id": entity_id,
        "recommendation_id": recommendation_id or external_record_id or crm_row_id,
        "department": "sales",
        "task_type": "crm_outcome",
        "measured_at": occurred_at,
        "measurement_status": "recorded",
        "metadata": {
            "crm_outcome_id": crm_row_id,
            "connector_type": connector_type,
            **dict(metadata or {}),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        client.table("intelligence_outcome_events").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.debug("crm_outcome_learning_mirror_skipped org_id=%s err=%s", org_id, exc)


def count_crm_outcomes(client: Any, org_id: str) -> int:
    try:
        result = (
            client.table("crm_recommendation_outcomes")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        return int(getattr(result, "count", None) or len(result.data or []))
    except Exception as exc:  # noqa: BLE001
        logger.debug("crm_outcome_count_skipped err=%s", exc)
        return 0
