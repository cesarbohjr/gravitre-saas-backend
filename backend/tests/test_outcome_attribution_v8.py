from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.memory_promotion_service import MemoryPromotionService, MemoryPromotionStatus
from app.services.outcome_attribution_service import (
    CONFIDENCE_NOTE,
    MIN_SAMPLE_SIZE,
    OutcomeAttributionService,
    maybe_record_hubspot_deal_outcome_baseline,
)
from app.services.tool_types import ToolContext


def _mock_outcome_rows(count: int, *, measured: bool = True, positive: bool = True) -> list[dict]:
    rows = []
    for i in range(count):
        before = 100.0
        after = 150.0 if positive else 50.0
        row = {
            "id": f"row-{i}",
            "metric_value_before": before,
            "metric_value_after": after if measured else None,
            "measured_at": datetime.now(timezone.utc).isoformat() if measured else None,
            "confidence_note": CONFIDENCE_NOTE,
            "action_taken_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "attribution_window_days": 14,
            "target_entity_type": "deal",
            "target_entity_id": f"deal-{i}",
            "metric_name": "deal_amount",
        }
        rows.append(row)
    return rows


@pytest.mark.asyncio
async def test_baseline_only_recorded_for_observable_metrics():
    service = OutcomeAttributionService(settings=MagicMock())
    with patch.object(service, "_client") as mock_client:
        mock_client.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "1"}]
        )
        result = await service.record_action_baseline(
            "org-1",
            agent_id="agent-1",
            workflow_run_id=None,
            target_entity_type="deal",
            target_entity_id="deal-1",
            action_type="hubspot.deals.update",
            metric_name="deal_amount",
            metric_value_before=None,
        )
        assert result is None
        mock_client.return_value.table.return_value.insert.assert_not_called()

        result = await service.record_action_baseline(
            "org-1",
            agent_id="agent-1",
            workflow_run_id=None,
            target_entity_type="deal",
            target_entity_id="deal-1",
            action_type="hubspot.deals.update",
            metric_name="deal_amount",
            metric_value_before=5000.0,
        )
        assert result is not None


@pytest.mark.asyncio
async def test_measurement_waits_for_attribution_window():
    service = OutcomeAttributionService(settings=MagicMock())
    pending_row = {
        "id": "pending-1",
        "action_taken_at": datetime.now(timezone.utc).isoformat(),
        "attribution_window_days": 14,
        "target_entity_type": "deal",
        "target_entity_id": "deal-1",
        "metric_name": "deal_amount",
    }
    due_row = {
        **pending_row,
        "id": "due-1",
        "action_taken_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.is_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[pending_row, due_row]
    )
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
    with patch.object(service, "_client", return_value=client):
        with patch.object(service, "_fetch_current_metric_value", new=AsyncMock(return_value=6000.0)):
            measured = await service.measure_outcomes_due("org-1")
    assert measured == 1


@pytest.mark.asyncio
async def test_summary_requires_minimum_sample_size():
    service = OutcomeAttributionService(settings=MagicMock())
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.not_.is_.return_value.execute.return_value = MagicMock(
        data=_mock_outcome_rows(5)
    )
    with patch.object(service, "_client", return_value=client):
        summary = await service.get_agent_outcome_summary("org-1", "agent-1")
    assert summary["sampleSize"] == 5
    assert summary["sufficientData"] is False


@pytest.mark.asyncio
async def test_summary_below_threshold_states_insufficient_data():
    service = OutcomeAttributionService(settings=MagicMock())
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.not_.is_.return_value.execute.return_value = MagicMock(
        data=_mock_outcome_rows(MIN_SAMPLE_SIZE - 1)
    )
    with patch.object(service, "_client", return_value=client):
        summary = await service.get_agent_outcome_summary("org-1", "agent-1")
    assert summary["message"] == "insufficient data to draw a conclusion"
    assert summary["winRate"] is None


@pytest.mark.asyncio
async def test_confidence_note_present_on_every_row():
    service = OutcomeAttributionService(settings=MagicMock())
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"confidence_note": CONFIDENCE_NOTE}]
    )
    with patch.object(service, "_client", return_value=client):
        row = await service.record_action_baseline(
            "org-1",
            agent_id="agent-1",
            workflow_run_id=None,
            target_entity_type="deal",
            target_entity_id="deal-1",
            action_type="hubspot.deals.update",
            metric_name="deal_amount",
            metric_value_before=100.0,
        )
    assert row["confidence_note"] == CONFIDENCE_NOTE
    insert_payload = client.table.return_value.insert.call_args.args[0]
    assert insert_payload["confidence_note"] == CONFIDENCE_NOTE


@pytest.mark.asyncio
async def test_outcome_candidates_always_pending_approval():
    service = MemoryPromotionService(settings=MagicMock())
    with patch.object(service, "_client", return_value=MagicMock()):
        with patch(
            "app.services.outcome_attribution_service.get_outcome_attribution_service",
            return_value=MagicMock(
                get_agent_outcome_summary=AsyncMock(
                    return_value={
                        "sufficientData": True,
                        "winRate": 0.8,
                        "sampleSize": 20,
                        "avgMetricDelta": 100.0,
                    }
                )
            ),
        ):
            with patch.object(
                service,
                "_upsert_candidate",
                return_value={"status": MemoryPromotionStatus.PENDING_APPROVAL.value},
            ) as upsert:
                service._client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"id": "agent-1", "name": "Sales Agent"}]
                )
                created = await service.detect_outcome_pattern_candidates("org-1")
    assert created
    assert upsert.call_args.kwargs["status"] == MemoryPromotionStatus.PENDING_APPROVAL.value
    assert upsert.call_args.kwargs["candidate_type"] == "outcome_pattern"


def test_no_rl_policy_or_reward_function_introduced():
    import app.services.outcome_attribution_service as module
    import inspect

    source = inspect.getsource(module.OutcomeAttributionService).lower()
    forbidden = ["reward function", "reward_maxim", "learned policy", "q-learning", "policy gradient", "reinforcementlearning"]
    for term in forbidden:
        assert term not in source.replace(" ", "")
    assert "class reward" not in source


def test_maybe_record_skips_when_amount_missing():
    ctx = ToolContext(
        settings=MagicMock(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-1",
    )
    with patch("app.services.outcome_attribution_service.get_deal", return_value={"properties": {}}):
        maybe_record_hubspot_deal_outcome_baseline(
            ctx,
            deal_id="deal-1",
            action_type="hubspot.deals.update",
            token="token",
        )
    ctx.client.table.assert_not_called()
