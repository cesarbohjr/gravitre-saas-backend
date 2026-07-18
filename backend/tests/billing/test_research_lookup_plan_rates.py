"""Tests for billing_plans-backed research lookup rates."""
from __future__ import annotations

from app.billing.research_lookup_plan_rates import (
    included_research_lookups_for_plan,
    overage_usd_per_research_lookup,
)


def test_included_from_plan_features():
    plan = {"code": "control", "features": {"research_lookups_per_month": 60}}
    assert included_research_lookups_for_plan(plan) == 60


def test_overage_rate_from_plan():
    plan = {"code": "node", "overage_rates": {"research_lookup": 0.35}}
    assert overage_usd_per_research_lookup(plan) == 0.35


def test_fallback_when_plan_missing_keys():
    assert included_research_lookups_for_plan(None, plan_code="command") == 200
    assert overage_usd_per_research_lookup(None) == 0.35
