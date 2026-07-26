"""Summarize usage_records for billing surfaces (outputs, research lookups, etc.)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client

from app.billing.research_lookup_plan_rates import (
    included_research_lookups_for_plan,
    overage_usd_per_research_lookup,
)
from app.billing.service import get_plan_for_org
from app.config import Settings


def current_month_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc).isoformat()


def _included_outputs_for_tier(tier: str | None) -> int | None:
    mapping = {"free": 1000, "node": 10, "control": 40, "command": 120}
    return mapping.get(str(tier or "free").lower())


def summarize_usage_records_billing(
    client: Client,
    org_id: str,
    *,
    tier: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Aggregate usage_records for billing-usage / billing overview APIs."""
    month_start = current_month_start_iso()
    plan = get_plan_for_org(client, org_id)
    resolved_tier = str(tier or plan.get("code") or "free").strip().lower()

    usage_resp = (
        client.table("usage_records")
        .select("metric_type, quantity, recorded_at")
        .eq("org_id", org_id)
        .gte("recorded_at", month_start)
        .execute()
    )
    if usage_resp.error:
        raise RuntimeError(str(usage_resp.error))

    totals: dict[str, int] = {
        "outputs": 0,
        "workflow_runs": 0,
        "api_calls": 0,
        "ai_tokens": 0,
        "research_lookups": 0,
    }
    for row in usage_resp.data or []:
        metric = str(row.get("metric_type") or "")
        quantity = int(row.get("quantity") or 0)
        if metric in totals:
            totals[metric] += quantity

    included_outputs = _included_outputs_for_tier(resolved_tier)
    output_total = totals["outputs"]
    overage_outputs = max(output_total - included_outputs, 0) if included_outputs is not None else 0
    overage_cost_usd = round(overage_outputs * 0.01, 2)

    included_research = included_research_lookups_for_plan(plan, plan_code=resolved_tier)
    research_rate = overage_usd_per_research_lookup(plan)
    research_total = totals["research_lookups"]
    overage_research = max(research_total - included_research, 0)
    overage_research_usd = round(overage_research * research_rate, 2)
    remaining_research = max(included_research - research_total, 0)

    internet_research_enabled = bool(
        settings and getattr(settings, "internet_research_enabled", True)
    )

    return {
        "period_start": month_start,
        "tier": resolved_tier,
        "plan": plan,
        "totals": totals,
        "included_outputs": included_outputs,
        "overage_outputs": overage_outputs,
        "overage_cost_usd": overage_cost_usd,
        "included_research_lookups": included_research,
        "remaining_research_lookups": remaining_research,
        "overage_research_lookups": overage_research,
        "overage_research_cost_usd": overage_research_usd,
        "research_lookup_overage_rate_usd": research_rate,
        "internet_research_enabled": internet_research_enabled,
        "research_lookups_billing_visible": internet_research_enabled,
    }
