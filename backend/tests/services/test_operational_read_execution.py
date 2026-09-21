from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.operational_read_execution import try_operational_read_short_circuit_turn
from app.services.tool_types import NormalizedResult


@pytest.mark.asyncio
async def test_pipeline_health_disconnected_is_connect_guidance() -> None:
    turn = await try_operational_read_short_circuit_turn(
        message="How is the pipeline this month?",
        org_id="org-1",
        client=object(),
        settings=None,
        connected_integrations=["google_analytics"],
        task_state={},
    )
    assert turn is not None
    assert turn["workflow_status"] == "connector_not_connected"
    assert "analytics source" not in str(turn["message"]).lower()
    assert "connect" in str(turn["message"]).lower()


@pytest.mark.asyncio
async def test_pipeline_health_uses_deals_list_not_search() -> None:
    invoked = NormalizedResult(
        success=True,
        action="hubspot.deals.list",
        connector_id="hubspot",
        data={"results": [{"id": "1"}, {"id": "2"}]},
    )
    proof = MagicMock(ok=True, error_class=None)
    obs = MagicMock(success=True)
    with patch(
        "app.services.operational_read_execution.invoke_sealed_f1_read",
        return_value=(invoked, proof, obs),
    ) as mock_invoke:
        turn = await try_operational_read_short_circuit_turn(
            message="Show my deals",
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state={},
        )
    assert turn is not None
    assert turn["workflow_status"] == "completed"
    assert "2 deal" in str(turn["message"])
    assert mock_invoke.call_args.kwargs["action_key"] == "hubspot.deals.list"


@pytest.mark.asyncio
async def test_provider_error_is_failed_not_completed() -> None:
    invoked = NormalizedResult(
        success=False,
        action="hubspot.deals.list",
        connector_id="hubspot",
        error_code="provider_error",
        error_message="HubSpot timed out",
    )
    proof = MagicMock(ok=True, error_class=None)
    obs = MagicMock(success=False, step_id="read_sales_pipeline_health", connector_id="hubspot", summary="err")
    with patch(
        "app.services.operational_read_execution.invoke_sealed_f1_read",
        return_value=(invoked, proof, obs),
    ):
        turn = await try_operational_read_short_circuit_turn(
            message="Show my deals",
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state={},
        )
    assert turn["workflow_status"] == "failed"
    assert "timed out" in str(turn["message"]).lower() or "couldn't complete" in str(turn["message"]).lower()
