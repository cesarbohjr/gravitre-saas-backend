"""Tests for billing_plans-backed output/workflow/AI credit rates."""
from __future__ import annotations

from app.billing.plan_rates import (
    included_ai_credits_for_plan,
    included_outputs_for_plan,
    included_workflow_runs_for_plan,
    overage_usd_per_output,
)


def test_included_outputs_from_plan_features():
    plan = {"code": "control", "features": {"outputs_per_month": 40}}
    assert included_outputs_for_plan(plan) == 40


def test_unlimited_outputs_returns_none():
    plan = {"code": "enterprise", "features": {"outputs_per_month": -1}}
    assert included_outputs_for_plan(plan) is None


def test_output_overage_rate_from_plan():
    plan = {"code": "node", "overage_rates": {"output": 2.50}}
    assert overage_usd_per_output(plan) == 2.50


def test_workflow_runs_from_plan_column():
    plan = {"code": "command", "workflow_runs_included": 10000}
    assert included_workflow_runs_for_plan(plan) == 10000


def test_ai_credits_from_plan_column():
    plan = {"code": "node", "ai_credits_included": 1000}
    assert included_ai_credits_for_plan(plan) == 1000


def test_fallback_when_plan_missing_keys():
    assert included_outputs_for_plan(None, plan_code="node") == 10
    assert included_outputs_for_plan(None, plan_code="control") == 40
    assert included_workflow_runs_for_plan(None, plan_code="control") == 2500
    assert included_ai_credits_for_plan(None, plan_code="command") == 15000
    assert overage_usd_per_output(None) == 2.50
    assert overage_usd_per_output({"code": "command"}) == 1.50
