"""Plan allotments and overage rates — read from billing_plans (DB source of truth).

Canonical values: supabase/migrations/20260729120000_seed_all_billing_plans.sql
"""
from __future__ import annotations

from typing import Any

# Fallback when billing_plans row lacks keys (pre-migration or partial seed).
# Values match supabase/migrations/20260729120000_seed_all_billing_plans.sql
# and 20260719120000_billing_plans_research_lookups.sql.
_FALLBACK_OUTPUTS: dict[str, int | None] = {
    "free": 0,
    "node": 10,
    "control": 40,
    "command": 120,
    "enterprise": None,
    "starter": 10,
    "growth": 40,
    "scale": 120,
}
_FALLBACK_OUTPUT_OVERAGE_USD: dict[str, float] = {
    "node": 2.50,
    "control": 2.00,
    "command": 1.50,
    "starter": 2.50,
    "growth": 2.00,
    "scale": 1.50,
}
_FALLBACK_WORKFLOW_RUNS: dict[str, int] = {
    "free": 200,
    "node": 500,
    "control": 2500,
    "command": 10000,
    "enterprise": 0,
    "starter": 500,
    "growth": 2500,
    "scale": 10000,
}
_FALLBACK_AI_CREDITS: dict[str, int] = {
    "free": 0,
    "node": 1000,
    "control": 5000,
    "command": 15000,
    "enterprise": 0,
    "starter": 1000,
    "growth": 5000,
    "scale": 15000,
}


def _plan_code(plan: dict[str, Any] | None, plan_code: str | None = None) -> str:
    if plan_code:
        return str(plan_code).strip().lower()
    if plan:
        return str(plan.get("code") or "node").strip().lower()
    return "node"


def included_outputs_for_plan(
    plan: dict[str, Any] | None,
    *,
    plan_code: str | None = None,
) -> int | None:
    code = _plan_code(plan, plan_code)
    if plan:
        features = plan.get("features") if isinstance(plan.get("features"), dict) else {}
        raw = features.get("outputs_per_month")
        if raw is not None:
            try:
                value = int(raw)
                if value < 0:
                    return None
                return max(value, 0)
            except (TypeError, ValueError):
                pass
    fallback = _FALLBACK_OUTPUTS.get(code, _FALLBACK_OUTPUTS["node"])
    return fallback


def overage_usd_per_output(plan: dict[str, Any] | None) -> float:
    if plan:
        rates = plan.get("overage_rates") if isinstance(plan.get("overage_rates"), dict) else {}
        raw = rates.get("output")
        if raw is not None:
            try:
                return max(float(raw), 0.0)
            except (TypeError, ValueError):
                pass
    code = _plan_code(plan)
    return float(_FALLBACK_OUTPUT_OVERAGE_USD.get(code, _FALLBACK_OUTPUT_OVERAGE_USD["node"]))


def included_workflow_runs_for_plan(
    plan: dict[str, Any] | None,
    *,
    plan_code: str | None = None,
) -> int:
    code = _plan_code(plan, plan_code)
    if plan:
        raw = plan.get("workflow_runs_included")
        if raw is not None:
            try:
                return max(int(raw), 0)
            except (TypeError, ValueError):
                pass
    return int(_FALLBACK_WORKFLOW_RUNS.get(code, _FALLBACK_WORKFLOW_RUNS["node"]))


def included_ai_credits_for_plan(
    plan: dict[str, Any] | None,
    *,
    plan_code: str | None = None,
) -> int:
    code = _plan_code(plan, plan_code)
    if plan:
        raw = plan.get("ai_credits_included")
        if raw is not None:
            try:
                return max(int(raw), 0)
            except (TypeError, ValueError):
                pass
    return int(_FALLBACK_AI_CREDITS.get(code, _FALLBACK_AI_CREDITS["node"]))
