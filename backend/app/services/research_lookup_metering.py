"""Research Lookup metering — single pass for customer usage + internal cost tracking.

Customer-facing: Research Lookups (pricing-page family, separate from ai_credit LLM ledger).
Internal: records lookup count, estimated Gemini tokens, grounding count for COGS visibility.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from supabase import Client

from app.billing.research_lookup_plan_rates import (
    included_research_lookups_for_plan,
    overage_usd_per_research_lookup,
)
from app.billing.service import derive_idempotency_key, get_plan_for_org
from app.core.logging import get_logger

logger = get_logger(__name__)

# Allotments and overage rate: billing_plans.features.research_lookups_per_month +
# billing_plans.overage_rates.research_lookup (see research_lookup_plan_rates.py).
ESTIMATED_GROUNDING_COGS_USD_PER_LOOKUP_AT_FREE_TIER = 0.0
ESTIMATED_GROUNDING_COGS_USD_PER_LOOKUP_AT_PAID_TIER = 0.035  # $35/1k worst-case safety reference


def included_lookups_for_plan_code(plan_code: str | None, plan: dict | None = None) -> int:
    return included_research_lookups_for_plan(plan, plan_code=plan_code)


def overage_usd_per_lookup_for_plan(plan: dict | None) -> float:
    return overage_usd_per_research_lookup(plan)


def _month_start() -> date:
    now = datetime.now(timezone.utc)
    return date(now.year, now.month, 1)


def _month_end(start: date) -> date:
    if start.month == 12:
        return date(start.year + 1, 1, 1)
    return date(start.year, start.month + 1, 1)


def estimate_internal_cogs_usd(*, grounding_count: int = 1, input_tokens: int = 0, output_tokens: int = 0) -> dict[str, Any]:
    """Single place for lookup → internal cost mapping (gate 3 requirement)."""
    tokens = max(int(input_tokens or 0), 0) + max(int(output_tokens or 0), 0)
    # Flash-scale token COGS order-of-magnitude (~$0.0001/1k tokens blended) — for tracking not invoicing.
    token_cogs = round(tokens * 0.0000001, 6)
    grounding_cogs = ESTIMATED_GROUNDING_COGS_USD_PER_LOOKUP_AT_FREE_TIER * max(int(grounding_count or 1), 1)
    return {
        "grounding_count": max(int(grounding_count or 1), 1),
        "input_tokens": max(int(input_tokens or 0), 0),
        "output_tokens": max(int(output_tokens or 0), 0),
        "grounding_cogs_usd": grounding_cogs,
        "token_cogs_usd": token_cogs,
        "total_cogs_usd": round(grounding_cogs + token_cogs, 6),
        "cogs_basis": "free_tier_grounding_expected_at_current_scale",
    }


def record_research_lookup(
    client: Client,
    *,
    org_id: str,
    provider: str,
    query_hash: str,
    grounding_count: int = 1,
    input_tokens: int = 0,
    output_tokens: int = 0,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Record one Research Lookup for org billing + internal COGS metadata."""
    period_start = _month_start()
    period_end = _month_end(period_start)
    cogs = estimate_internal_cogs_usd(
        grounding_count=grounding_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    metadata = {
        "source": "research_lookup",
        "source_id": source_id or query_hash,
        "provider": provider,
        **cogs,
    }

    idempotency_key = derive_idempotency_key(
        org_id,
        "research_lookups",
        period_start,
        metadata={"source": "research_lookup", "source_id": metadata["source_id"]},
    )

    payload = {
        "org_id": org_id,
        "metric_type": "research_lookups",
        "quantity": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "idempotency_key": idempotency_key,
    }

    inserted = False
    try:
        resp = (
            client.table("usage_records")
            .upsert(payload, on_conflict="org_id,idempotency_key", ignore_duplicates=True)
            .execute()
        )
        inserted = bool(resp.data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("research_lookup_usage_insert_failed org_id=%s error=%s", org_id, str(exc))
        try:
            client.table("usage_records").insert(payload).execute()
            inserted = True
        except Exception as inner:  # noqa: BLE001
            logger.warning("research_lookup_usage_fallback_failed org_id=%s error=%s", org_id, str(inner))

    plan = get_plan_for_org(client, org_id)
    plan_code = str(plan.get("code") or "node")
    included = included_research_lookups_for_plan(plan, plan_code=plan_code)
    overage_rate = overage_usd_per_research_lookup(plan)

    month_total = 0
    try:
        rows = (
            client.table("usage_records")
            .select("quantity")
            .eq("org_id", org_id)
            .eq("metric_type", "research_lookups")
            .gte("recorded_at", period_start.isoformat())
            .execute()
            .data
            or []
        )
        month_total = sum(int(r.get("quantity") or 0) for r in rows)
    except Exception:  # noqa: BLE001
        pass

    overage = max(month_total - included, 0)
    return {
        "recorded": inserted,
        "org_id": org_id,
        "plan_code": plan_code,
        "included_lookups_per_month": included,
        "month_total_lookups": month_total,
        "overage_lookups": overage,
        "overage_usd_estimate": round(overage * overage_rate, 2) if overage else 0.0,
        "overage_rate_usd": overage_rate,
        "internal_cogs": cogs,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }
