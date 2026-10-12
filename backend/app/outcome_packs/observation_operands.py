"""Phase 5: customer observations as predicate operands.

A recipe can test an account's observation trends with ordinary field paths,
for example ``observations.sentiment.direction eq rising`` or
``observations.support_friction.latest_mean lte 0``. The measurement engine
adds ``observations`` to the record only for recipes that reference it, so
existing recipes read exactly what they read before.

Each dimension resolves to the same trend the account card shows: direction
(``rising`` / ``falling`` / ``steady`` / ``insufficient_evidence``),
``latest_mean``, ``delta`` and ``observations``. Trends without enough
evidence carry no ``latest_mean``, so a comparison on them never passes.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

PREFIX = "observations."
WINDOW_DAYS = 30


def _pred_fields(pred: Any) -> list[str]:
    if pred is None:
        return []
    out: list[str] = []
    for child in (pred.all or []) + (pred.any or []):
        out.extend(_pred_fields(child))
    out.extend(f for f in (pred.field, pred.value_field) if f)
    return out


def recipe_uses_observations(recipe: Any) -> bool:
    fields: list[str] = []
    for c in getattr(recipe, "contributions", []) or []:
        fields += _pred_fields(c.when) + _pred_fields(c.fail_when)
        for expr in (c.value, c.baseline):
            fields += [f for f in (expr.field, expr.duration_from, expr.duration_to) if f]
    return any(f.startswith(PREFIX) for f in fields)


def observation_operands(
    client: Any,
    org_id: str,
    *,
    system: str,
    record_type: str,
    record_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Trends per dimension for the account bound to a source record, or {}."""
    from app.services.entity_observations import DIMENSIONS, trend

    now = now or datetime.now(UTC)
    try:
        bindings = (
            client.table("org_business_entity_bindings")
            .select("entity_id")
            .eq("org_id", org_id)
            .eq("system", system)
            .eq("resource_type", record_type)
            .eq("resource_id", record_id)
            .limit(2)
            .execute()
            .data
            or []
        )
        entity_ids = {str(b["entity_id"]) for b in bindings if b.get("entity_id")}
        if len(entity_ids) != 1:
            return {}
        rows = (
            client.table("entity_observations")
            .select("dimension, score, observed_at, status, correction, source_system, source_record_id")
            .eq("org_id", org_id)
            .eq("entity_id", entity_ids.pop())
            .gte("observed_at", (now - timedelta(days=WINDOW_DAYS)).isoformat())
            .limit(500)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("observation_operands_failed org_id=%s error=%s", org_id, type(exc).__name__)
        return {}
    out: dict[str, Any] = {}
    for dim in DIMENSIONS:
        t = trend(rows, dimension=dim, now=now, window_days=WINDOW_DAYS)
        out[dim] = {k: t[k] for k in ("direction", "observations", "latest_mean", "delta") if k in t}
    return out
