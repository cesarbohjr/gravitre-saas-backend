"""Item 4 — capture CRM outcome labels for future learning (no ML).

Write path only when a connector/sync emits a real event. Never invent labels.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

CRM_OUTCOME_TYPES = frozenset({"contacted", "replied", "booked", "won", "lost"})


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
    """Persist one labeled CRM outcome. Raises ValueError on invalid type."""
    outcome = str(outcome_type or "").strip().lower()
    if outcome not in CRM_OUTCOME_TYPES:
        raise ValueError(f"Invalid CRM outcome_type: {outcome_type}")

    row = {
        "id": str(uuid4()),
        "org_id": org_id,
        "outcome_type": outcome,
        "connector_type": (connector_type or "").strip().lower() or None,
        "external_record_id": (external_record_id or "").strip() or None,
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
    return {"stored": True, "id": row["id"], "outcomeType": outcome}


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
