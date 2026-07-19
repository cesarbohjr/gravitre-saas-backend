"""CF v1 interaction matrix — org × (connector | pack | card) scored events.

Hard rules:
- Advisory ranking signals only; never auto-execute.
- Cold start when volume gate fails (caller keeps heuristics order).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

MIN_SCORED_INTERACTIONS_30D = 50
LOOKBACK_DAYS = 30

# Positive / negative weights for soft-rank (gate counts rows, not weight sum).
WEIGHT_USAGE = 1.0
WEIGHT_ACCEPT = 2.0
WEIGHT_REJECT = -1.0
WEIGHT_DISMISS = -1.5
WEIGHT_CRM_POSITIVE = 2.0
WEIGHT_CRM_NEGATIVE = -1.0

CRM_POSITIVE = frozenset({"won", "booked", "accepted", "converted", "closed_won"})
CRM_NEGATIVE = frozenset({"lost", "rejected", "closed_lost", "churned"})


def item_key_connector(vendor: str) -> str:
    return f"connector:{str(vendor or '').strip().lower()}"


def item_key_pack(pack_id: str) -> str:
    return f"pack:{str(pack_id or '').strip().lower()}"


def item_key_card(card_id: str) -> str:
    return f"card:{str(card_id or '').strip()}"


def _cutoff_iso(lookback_days: int = LOOKBACK_DAYS) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=max(1, int(lookback_days)))).isoformat()


def _safe_rows(client: Any, table: str, builder) -> list[dict[str, Any]]:
    try:
        result = builder(client.table(table)).execute()
        return list(result.data or [])
    except Exception:  # noqa: BLE001
        return []


def load_scored_interactions(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    """Load org-scoped scored interactions for the CF soft-rank matrix."""
    cutoff = _cutoff_iso(lookback_days)
    rows: list[dict[str, Any]] = []

    # 1) Connector tool usage (audit_events via STA-123 helpers).
    try:
        from app.services.integration_suggestion_service import (
            aggregate_tool_usage,
            fetch_tool_usage_events,
        )

        events = fetch_tool_usage_events(client, org_id, lookback_days=lookback_days)
        summary = aggregate_tool_usage(events)
        for item in list(summary.get("connectors") or []):
            vendor = str(item.get("connectorType") or "").strip().lower()
            count = int(item.get("totalInvocations") or 0)
            if not vendor or count <= 0:
                continue
            # Cap contribution so a single hot connector cannot drown the gate alone.
            scored = min(count, 25)
            for _ in range(scored):
                rows.append(
                    {
                        "item_key": item_key_connector(vendor),
                        "weight": WEIGHT_USAGE,
                        "source": "tool_usage",
                    }
                )
    except Exception:  # noqa: BLE001
        pass

    # 2) Heuristic dismissals (negative on card ids).
    dismissals = _safe_rows(
        client,
        "heuristic_recommendation_dismissals",
        lambda t: t.select("card_id,dismissed_at")
        .eq("org_id", org_id)
        .gte("dismissed_at", cutoff),
    )
    for row in dismissals:
        card_id = str(row.get("card_id") or "").strip()
        if not card_id:
            continue
        rows.append(
            {
                "item_key": item_key_card(card_id),
                "weight": WEIGHT_DISMISS,
                "source": "dismiss",
            }
        )

    # 3) Assistant / intelligence accept-reject outcomes.
    outcomes = _safe_rows(
        client,
        "intelligence_outcome_events",
        lambda t: t.select("outcome_event,entity_id,recommendation_id,created_at")
        .eq("org_id", org_id)
        .gte("created_at", cutoff)
        .in_("outcome_event", ["recommendation_approved", "recommendation_rejected"]),
    )
    for row in outcomes:
        event_type = str(row.get("outcome_event") or "").strip().lower()
        rec_id = str(row.get("recommendation_id") or row.get("entity_id") or "").strip()
        if not rec_id:
            continue
        weight = WEIGHT_ACCEPT if event_type == "recommendation_approved" else WEIGHT_REJECT
        rows.append(
            {
                "item_key": item_key_card(rec_id),
                "weight": weight,
                "source": event_type,
            }
        )

    # 4) CRM recommendation outcomes.
    crm_rows = _safe_rows(
        client,
        "crm_recommendation_outcomes",
        lambda t: t.select("outcome_type,recommendation_id,connector_type,occurred_at")
        .eq("org_id", org_id)
        .gte("occurred_at", cutoff),
    )
    for row in crm_rows:
        outcome = str(row.get("outcome_type") or "").strip().lower()
        rec_id = str(row.get("recommendation_id") or "").strip()
        vendor = str(row.get("connector_type") or "").strip().lower()
        if outcome in CRM_POSITIVE:
            weight = WEIGHT_CRM_POSITIVE
        elif outcome in CRM_NEGATIVE:
            weight = WEIGHT_CRM_NEGATIVE
        else:
            continue
        if rec_id:
            rows.append(
                {
                    "item_key": item_key_card(rec_id),
                    "weight": weight,
                    "source": f"crm:{outcome}",
                }
            )
        if vendor:
            rows.append(
                {
                    "item_key": item_key_connector(vendor),
                    "weight": weight * 0.5,
                    "source": f"crm_connector:{outcome}",
                }
            )

    return rows


def count_scored_interactions(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = LOOKBACK_DAYS,
) -> int:
    return len(load_scored_interactions(client, org_id, lookback_days=lookback_days))


def training_gate_status(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = LOOKBACK_DAYS,
) -> dict[str, Any]:
    current = count_scored_interactions(client, org_id, lookback_days=lookback_days)
    return {
        "model": "cf_soft_ranker",
        "lookback_days": lookback_days,
        "current": current,
        "required": MIN_SCORED_INTERACTIONS_30D,
        "ready": current >= MIN_SCORED_INTERACTIONS_30D,
        "advisory_only": True,
        "cold_start": current < MIN_SCORED_INTERACTIONS_30D,
    }


def item_affinity_scores(interactions: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate weight per item_key for soft-rank."""
    scores: dict[str, float] = {}
    for row in interactions:
        key = str(row.get("item_key") or "").strip()
        if not key:
            continue
        scores[key] = float(scores.get(key) or 0.0) + float(row.get("weight") or 0.0)
    return scores
