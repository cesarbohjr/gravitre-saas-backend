"""Summarize usage_records for billing surfaces (outputs, research lookups, etc.)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client

from app.billing.plan_rates import (
    included_ai_credits_for_plan,
    included_outputs_for_plan,
    included_workflow_runs_for_plan,
    overage_usd_per_output,
)
from app.billing.research_lookup_plan_rates import (
    included_research_lookups_for_plan,
    overage_usd_per_research_lookup,
)
from app.billing.service import get_plan_for_org
from app.billing.voice_minutes_plan_rates import (
    included_voice_minutes_for_plan,
    overage_usd_per_voice_minute,
)
from app.config import Settings


def current_month_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc).isoformat()


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
    # org_billing-backed plan.code is canonical; a stale subscriptions.tier must not win.
    resolved_tier = str(plan.get("code") or tier or "free").strip().lower()

    usage_resp = (
        client.table("usage_records")
        .select("metric_type, quantity, recorded_at")
        .eq("org_id", org_id)
        .gte("recorded_at", month_start)
        .execute()
    )
    # supabase-py v2 APIResponse has data/count only — .error raises AttributeError
    # and was 500ing GET /api/billing (Billing page: Plan unavailable).
    usage_err = getattr(usage_resp, "error", None)
    if usage_err:
        raise RuntimeError(str(usage_err))

    totals: dict[str, int] = {
        "outputs": 0,
        "workflow_runs": 0,
        "api_calls": 0,
        "ai_tokens": 0,
        "research_lookups": 0,
        "voice_minutes": 0,
    }
    for row in usage_resp.data or []:
        metric = str(row.get("metric_type") or "")
        quantity = int(row.get("quantity") or 0)
        if metric in totals:
            totals[metric] += quantity

    included_outputs = included_outputs_for_plan(plan, plan_code=resolved_tier)
    output_rate = overage_usd_per_output(plan)
    output_total = totals["outputs"]
    if included_outputs is None:
        overage_outputs = 0
    else:
        overage_outputs = max(output_total - included_outputs, 0)
    overage_cost_usd = round(overage_outputs * output_rate, 2)

    workflow_runs_included = included_workflow_runs_for_plan(plan, plan_code=resolved_tier)
    ai_credits_included = included_ai_credits_for_plan(plan, plan_code=resolved_tier)

    included_research = included_research_lookups_for_plan(plan, plan_code=resolved_tier)
    research_rate = overage_usd_per_research_lookup(plan)
    research_total = totals["research_lookups"]
    overage_research = max(research_total - included_research, 0)
    overage_research_usd = round(overage_research * research_rate, 2)
    remaining_research = max(included_research - research_total, 0)

    internet_research_enabled = bool(
        settings and getattr(settings, "internet_research_enabled", True)
    )

    included_voice = included_voice_minutes_for_plan(plan, plan_code=resolved_tier)
    voice_rate = overage_usd_per_voice_minute(plan)
    voice_total = totals["voice_minutes"]
    overage_voice = max(voice_total - included_voice, 0)
    overage_voice_usd = round(overage_voice * voice_rate, 2)
    remaining_voice = max(included_voice - voice_total, 0)
    # Visibility: Meson voice_interface addon (when entitlements available on settings caller).
    voice_minutes_billing_visible = True

    return {
        "period_start": month_start,
        "tier": resolved_tier,
        "plan": plan,
        "totals": totals,
        "included_outputs": included_outputs,
        "workflow_runs_included": workflow_runs_included,
        "ai_credits_included": ai_credits_included,
        "overage_outputs": overage_outputs,
        "overage_cost_usd": overage_cost_usd,
        "output_overage_rate_usd": output_rate,
        "included_research_lookups": included_research,
        "remaining_research_lookups": remaining_research,
        "overage_research_lookups": overage_research,
        "overage_research_cost_usd": overage_research_usd,
        "research_lookup_overage_rate_usd": research_rate,
        "internet_research_enabled": internet_research_enabled,
        "research_lookups_billing_visible": internet_research_enabled,
        "included_voice_minutes": included_voice,
        "remaining_voice_minutes": remaining_voice,
        "overage_voice_minutes": overage_voice,
        "overage_voice_cost_usd": overage_voice_usd,
        "voice_minute_overage_rate_usd": voice_rate,
        "voice_minutes_billing_visible": voice_minutes_billing_visible,
    }
