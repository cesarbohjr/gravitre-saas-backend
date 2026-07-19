"""CF interaction matrix — actor × (connector | pack | card) scored events.

Hard rules:
- Advisory ranking signals only; never auto-execute.
- Cold start when volume gate fails (caller keeps heuristics order).
- Rows include actor_id for matrix factorization (user × item).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

MIN_SCORED_INTERACTIONS_30D = 50
LOOKBACK_DAYS = 30
ORG_ACTOR_PREFIX = "org:"

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


def _org_actor(org_id: str) -> str:
    return f"{ORG_ACTOR_PREFIX}{org_id}"


def _actor_from_metadata(meta: Any, *, fallback: str) -> str:
    if isinstance(meta, dict):
        for key in ("user_id", "userId", "actor_id", "actorId", "sub"):
            value = str(meta.get(key) or "").strip()
            if value:
                return value
    return fallback


def load_scored_interactions(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    """Load org-scoped scored interactions for CF soft-rank / matrix factorization."""
    cutoff = _cutoff_iso(lookback_days)
    rows: list[dict[str, Any]] = []
    org_actor = _org_actor(org_id)

    # 1) Connector tool usage (audit_events via STA-123 helpers).
    try:
        from app.services.integration_suggestion_service import (
            aggregate_tool_usage,
            fetch_tool_usage_events,
        )

        events = fetch_tool_usage_events(client, org_id, lookback_days=lookback_days)
        # Prefer per-event actors when present; also keep aggregate connector signal.
        per_vendor: dict[str, int] = {}
        for event in events:
            meta = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
            vendor = str(
                meta.get("connector_type")
                or meta.get("connectorType")
                or meta.get("vendor")
                or ""
            ).strip().lower()
            if not vendor:
                continue
            actor = _actor_from_metadata(meta, fallback=f"usage:{vendor}")
            rows.append(
                {
                    "actor_id": actor,
                    "item_key": item_key_connector(vendor),
                    "weight": WEIGHT_USAGE,
                    "source": "tool_usage_event",
                }
            )
            per_vendor[vendor] = per_vendor.get(vendor, 0) + 1

        summary = aggregate_tool_usage(events)
        for item in list(summary.get("connectors") or []):
            vendor = str(item.get("connectorType") or "").strip().lower()
            count = int(item.get("totalInvocations") or 0)
            if not vendor or count <= 0:
                continue
            # Cap org-level aggregate so a hot connector cannot drown the gate alone.
            scored = min(count, 25)
            already = min(per_vendor.get(vendor, 0), scored)
            for _ in range(max(0, scored - already)):
                rows.append(
                    {
                        "actor_id": org_actor,
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
        lambda t: t.select("card_id,user_id,dismissed_at")
        .eq("org_id", org_id)
        .gte("dismissed_at", cutoff),
    )
    for row in dismissals:
        card_id = str(row.get("card_id") or "").strip()
        if not card_id:
            continue
        actor = str(row.get("user_id") or "").strip() or org_actor
        rows.append(
            {
                "actor_id": actor,
                "item_key": item_key_card(card_id),
                "weight": WEIGHT_DISMISS,
                "source": "dismiss",
            }
        )

    # 3) Assistant / intelligence accept-reject outcomes.
    outcomes = _safe_rows(
        client,
        "intelligence_outcome_events",
        lambda t: t.select("outcome_event,entity_id,recommendation_id,agent_id,created_at")
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
        actor = str(row.get("agent_id") or "").strip() or org_actor
        rows.append(
            {
                "actor_id": actor,
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
                    "actor_id": org_actor,
                    "item_key": item_key_card(rec_id),
                    "weight": weight,
                    "source": f"crm:{outcome}",
                }
            )
        if vendor:
            rows.append(
                {
                    "actor_id": org_actor,
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


def matrix_factorization_gate_status(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = LOOKBACK_DAYS,
) -> dict[str, Any]:
    """Stricter gate for full MF train (≥50 interactions, ≥2 actors, ≥3 items)."""
    from app.ml.cf_matrix_factorization import MIN_ITEMS, MIN_USERS

    interactions = load_scored_interactions(client, org_id, lookback_days=lookback_days)
    actors = {str(r.get("actor_id") or "") for r in interactions if r.get("actor_id")}
    items = {str(r.get("item_key") or "") for r in interactions if r.get("item_key")}
    current = len(interactions)
    ready = (
        current >= MIN_SCORED_INTERACTIONS_30D
        and len(actors) >= MIN_USERS
        and len(items) >= MIN_ITEMS
    )
    return {
        "model": "cf_matrix_factorizer",
        "lookback_days": lookback_days,
        "current": current,
        "required": MIN_SCORED_INTERACTIONS_30D,
        "actors": len(actors),
        "items": len(items),
        "min_actors": MIN_USERS,
        "min_items": MIN_ITEMS,
        "ready": ready,
        "advisory_only": True,
        "cold_start": not ready,
    }


def training_gate_status(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = LOOKBACK_DAYS,
) -> dict[str, Any]:
    current = count_scored_interactions(client, org_id, lookback_days=lookback_days)
    mf = matrix_factorization_gate_status(client, org_id, lookback_days=lookback_days)
    return {
        "model": "cf_soft_ranker",
        "lookback_days": lookback_days,
        "current": current,
        "required": MIN_SCORED_INTERACTIONS_30D,
        "ready": current >= MIN_SCORED_INTERACTIONS_30D,
        "advisory_only": True,
        "cold_start": current < MIN_SCORED_INTERACTIONS_30D,
        "matrix_factorization": mf,
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
