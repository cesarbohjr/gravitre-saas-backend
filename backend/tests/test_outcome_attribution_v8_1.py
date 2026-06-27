from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.outcome_attribution_service import (
    DEFAULT_ATTRIBUTION_WINDOW_DAYS,
    METRIC_SUBSCRIPTION_STATUS,
    get_attribution_window,
    maybe_record_stripe_subscription_outcome_baseline,
    OutcomeAttributionService,
)
from app.services.tool_types import ToolContext


@pytest.mark.asyncio
async def test_window_selected_by_action_type():
    service = OutcomeAttributionService(settings=MagicMock())
    with patch.object(service, "_client") as mock_client:
        mock_client.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "1"}]
        )
        await service.record_action_baseline(
            "org-1",
            agent_id="agent-1",
            workflow_run_id=None,
            target_entity_type="subscription",
            target_entity_id="sub-1",
            action_type="stripe.subscriptions.update",
            metric_name=METRIC_SUBSCRIPTION_STATUS,
            metric_value_before=1.0,
        )
        payload = mock_client.return_value.table.return_value.insert.call_args.args[0]
        assert payload["attribution_window_days"] == 30


def test_unknown_action_type_falls_back_to_default_window():
    assert get_attribution_window("unknown.action") == DEFAULT_ATTRIBUTION_WINDOW_DAYS
    assert get_attribution_window("hubspot.deals.update") == 14


@pytest.mark.asyncio
async def test_measurement_respects_per_action_window():
    service = OutcomeAttributionService(settings=MagicMock())
    pending_row = {
        "id": "pending-1",
        "action_taken_at": datetime.now(timezone.utc).isoformat(),
        "attribution_window_days": 30,
        "target_entity_type": "subscription",
        "target_entity_id": "sub-1",
        "metric_name": METRIC_SUBSCRIPTION_STATUS,
    }
    due_row = {
        **pending_row,
        "id": "due-1",
        "action_taken_at": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.is_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[pending_row, due_row]
    )
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
    with patch.object(service, "_client", return_value=client):
        with patch.object(service, "_fetch_current_metric_value", new=AsyncMock(return_value=0.5)):
            measured = await service.measure_outcomes_due("org-1")
    assert measured == 1


def test_stripe_subscription_update_records_baseline():
    ctx = ToolContext(
        settings=MagicMock(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-1",
        run_id="run-1",
    )
    ctx.client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])
    with patch(
        "app.services.outcome_attribution_service.get_supabase_client",
        return_value=ctx.client,
    ):
        maybe_record_stripe_subscription_outcome_baseline(
            ctx,
            subscription_id="sub_123",
            action_type="stripe.subscriptions.update",
            before_state={"status": "active", "mrr_cents": 9900.0},
        )
    payload = ctx.client.table.return_value.insert.call_args.args[0]
    assert payload["action_type"] == "stripe.subscriptions.update"
    assert payload["target_entity_type"] == "subscription"
    assert payload["metric_name"] == METRIC_SUBSCRIPTION_STATUS
    assert payload["attribution_window_days"] == 30


def test_no_rl_or_reward_logic_introduced():
    import app.services.outcome_attribution_service as module
    import inspect

    source = inspect.getsource(module.OutcomeAttributionService).lower()
    forbidden = [
        "reward function",
        "reward_maxim",
        "learned policy",
        "q-learning",
        "policy gradient",
        "reinforcementlearning",
    ]
    for term in forbidden:
        assert term not in source.replace(" ", "")
