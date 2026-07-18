"""Research Lookup allotments and overage rates — read from billing_plans (DB source of truth)."""
from __future__ import annotations

from typing import Any

# Fallback when billing_plans row lacks keys (pre-migration or partial seed).
_FALLBACK_INCLUDED: dict[str, int] = {
    "node": 10,
    "control": 60,
    "command": 200,
    "enterprise": 200,
    "free": 0,
    "starter": 10,
    "growth": 60,
    "scale": 200,
}
_FALLBACK_OVERAGE_USD = 0.35


def _plan_code(plan: dict[str, Any] | None, plan_code: str | None = None) -> str:
    if plan_code:
        return str(plan_code).strip().lower()
    if plan:
        return str(plan.get("code") or "node").strip().lower()
    return "node"


def included_research_lookups_for_plan(
    plan: dict[str, Any] | None,
    *,
    plan_code: str | None = None,
) -> int:
    code = _plan_code(plan, plan_code)
    if plan:
        features = plan.get("features") if isinstance(plan.get("features"), dict) else {}
        raw = features.get("research_lookups_per_month")
        if raw is not None:
            try:
                return max(int(raw), 0)
            except (TypeError, ValueError):
                pass
    return int(_FALLBACK_INCLUDED.get(code, _FALLBACK_INCLUDED["node"]))


def overage_usd_per_research_lookup(plan: dict[str, Any] | None) -> float:
    if plan:
        rates = plan.get("overage_rates") if isinstance(plan.get("overage_rates"), dict) else {}
        raw = rates.get("research_lookup")
        if raw is not None:
            try:
                return max(float(raw), 0.0)
            except (TypeError, ValueError):
                pass
    return _FALLBACK_OVERAGE_USD
