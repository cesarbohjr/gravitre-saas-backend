"""Tests for usage_records billing summary overage math."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.billing.usage_records_summary import summarize_usage_records_billing


def _usage_rows(*entries: tuple[str, int]) -> MagicMock:
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = MagicMock(
        error=None,
        data=[{"metric_type": metric, "quantity": qty, "recorded_at": "2026-07-01T00:00:00Z"} for metric, qty in entries],
    )
    return client


@patch("app.billing.usage_records_summary.get_plan_for_org")
def test_output_overage_uses_plan_rate(mock_get_plan):
    mock_get_plan.return_value = {
        "code": "node",
        "features": {"outputs_per_month": 10},
        "overage_rates": {"output": 2.50},
        "workflow_runs_included": 500,
        "ai_credits_included": 1000,
    }
    client = _usage_rows(("outputs", 15), ("workflow_runs", 0))

    summary = summarize_usage_records_billing(client, "org-1", tier="node")

    assert summary["included_outputs"] == 10
    assert summary["overage_outputs"] == 5
    assert summary["overage_cost_usd"] == 12.50
    assert summary["output_overage_rate_usd"] == 2.50
    assert summary["workflow_runs_included"] == 500
    assert summary["ai_credits_included"] == 1000


@patch("app.billing.usage_records_summary.get_plan_for_org")
def test_command_output_overage_rate(mock_get_plan):
    mock_get_plan.return_value = {
        "code": "command",
        "features": {"outputs_per_month": 120, "research_lookups_per_month": 200},
        "overage_rates": {"output": 1.50, "research_lookup": 0.35},
        "workflow_runs_included": 10000,
        "ai_credits_included": 15000,
    }
    client = _usage_rows(("outputs", 130))

    summary = summarize_usage_records_billing(client, "org-1", tier="command")

    assert summary["overage_outputs"] == 10
    assert summary["overage_cost_usd"] == 15.00
    assert summary["output_overage_rate_usd"] == 1.50
