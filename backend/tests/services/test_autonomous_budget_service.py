"""STA-109: autonomous run budgets."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.autonomous_budget_service import (
    AutonomousBudgetExceededError,
    build_budget_status,
    check_autonomous_budget,
    get_effective_budgets,
    record_autonomous_usage,
    record_autonomous_llm_usage,
    update_operator_run_budgets,
)


def _chainable(data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.update.return_value = mock
    mock.upsert.return_value = mock
    mock.execute.return_value = MagicMock(data=data or [], error=None)
    return mock


def test_effective_budgets_prefers_operator_over_org_defaults():
    client = MagicMock()

    def table_side_effect(name: str):
        if name == "organizations":
            return _chainable(
                [
                    {
                        "settings": {
                            "enterprise": {
                                "autonomousRunBudgets": {
                                    "maxActionsPerDay": 100,
                                    "maxTokensPerDay": 50000,
                                    "maxSpendUsdPerDay": 25,
                                }
                            }
                        }
                    }
                ]
            )
        return _chainable()

    client.table.side_effect = table_side_effect
    operator = {
        "id": "op-1",
        "auto_run_max_actions_per_day": 10,
        "auto_run_max_tokens_per_day": None,
        "auto_run_max_spend_usd_per_day": 5,
    }
    budgets = get_effective_budgets(client, "org-1", operator)
    assert budgets["maxActionsPerDay"] == 10
    assert budgets["maxTokensPerDay"] == 50000
    assert budgets["maxSpendUsdPerDay"] == 5


def test_check_budget_blocks_when_actions_exceeded():
    client = MagicMock()

    def table_side_effect(name: str):
        if name == "organizations":
            return _chainable([{"settings": {}}])
        if name == "operator_autonomous_usage_daily":
            return _chainable([{"action_count": 10, "token_count": 0, "spend_usd": 0}])
        return _chainable()

    client.table.side_effect = table_side_effect
    operator = {"id": "op-1", "auto_run_max_actions_per_day": 10}
    with pytest.raises(AutonomousBudgetExceededError) as exc:
        check_autonomous_budget(client, "org-1", operator, projected_actions=1)
    assert exc.value.dimension == "actions"


def test_record_autonomous_usage_upserts_daily_row():
    client = MagicMock()
    usage_table = _chainable([])
    client.table.side_effect = lambda name: usage_table if name == "operator_autonomous_usage_daily" else _chainable([])

    record_autonomous_usage(client, "org-1", "op-1", actions=2, tokens=100, spend_usd=1.5)
    usage_table.upsert.assert_called_once()
    payload = usage_table.upsert.call_args[0][0]
    assert payload["action_count"] == 2
    assert payload["token_count"] == 100
    assert payload["spend_usd"] == 1.5


def test_build_budget_status_returns_limits_and_usage():
    client = MagicMock()

    def table_side_effect(name: str):
        if name == "organizations":
            return _chainable([{"settings": {}}])
        if name == "operator_autonomous_usage_daily":
            return _chainable([{"action_count": 3, "token_count": 500, "spend_usd": 0.25}])
        return _chainable()

    client.table.side_effect = table_side_effect
    operator = {"id": "op-1", "auto_run_max_actions_per_day": 20}
    status = build_budget_status(client, "org-1", operator)
    assert status["limits"]["maxActionsPerDay"] == 20
    assert status["usageToday"]["actions"] == 3.0


def test_record_autonomous_llm_usage_increments_tokens_and_spend():
    client = MagicMock()
    usage_table = _chainable([])
    client.table.side_effect = lambda name: usage_table if name == "operator_autonomous_usage_daily" else _chainable([])

    record_autonomous_llm_usage(client, "org-1", "op-1", input_tokens=100, output_tokens=50, spend_usd=0.42)
    payload = usage_table.upsert.call_args[0][0]
    assert payload["token_count"] == 150
    assert payload["spend_usd"] == 0.42


def test_update_operator_run_budgets_writes_audit():
    client = MagicMock()
    operators = _chainable(
        [
            {
                "id": "op-1",
                "auto_run_max_actions_per_day": 5,
                "auto_run_max_tokens_per_day": 1000,
                "auto_run_max_spend_usd_per_day": 2,
            }
        ]
    )
    client.table.side_effect = lambda name: operators if name == "operators" else _chainable([])

    with patch("app.services.autonomous_budget_service.write_audit_event"):
        updated = update_operator_run_budgets(
            client,
            org_id="org-1",
            operator_id="op-1",
            max_actions_per_day=5,
            max_tokens_per_day=1000,
            max_spend_usd_per_day=2,
            actor_id="user-1",
        )
    assert updated["auto_run_max_actions_per_day"] == 5
