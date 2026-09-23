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
    arts = turn["task_state"].get("work_artifacts") or []
    assert arts
    assert arts[-1]["metadata"]["outcome"] == "blocked"
    assert turn["execution_result"]["success"] is False
    assert str(turn["task_state"]["execution_plan"]["terminal_status"]).lower() == "blocked"


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
    message = str(turn["message"])
    assert "2 deal" in message
    assert "What is happening:" in message
    assert "What appears important:" in message
    assert "What I cannot conclude:" in message
    assert "What is missing:" in message
    assert "What to do next:" in message
    assert mock_invoke.call_args.kwargs["action_key"] == "hubspot.deals.list"
    assert turn.get("execution_result")
    assert turn["task_state"].get("work_artifacts")
    assert turn["task_state"]["work_artifacts"][-1]["kind"] == "report"


@pytest.mark.asyncio
async def test_pipeline_synthesis_uses_stage_and_amount_without_inventing_traffic() -> None:
    invoked = NormalizedResult(
        success=True,
        action="hubspot.deals.list",
        connector_id="hubspot",
        data={
            "results": [
                {
                    "id": "1",
                    "properties": {
                        "dealname": "Acme renewal",
                        "dealstage": "contractsent",
                        "amount": "12000",
                    },
                },
                {
                    "id": "2",
                    "properties": {
                        "dealname": "Beta intro",
                        "dealstage": "appointmentscheduled",
                        "amount": "",
                    },
                },
            ]
        },
    )
    proof = MagicMock(ok=True, error_class=None)
    obs = MagicMock(success=True)
    with patch(
        "app.services.operational_read_execution.invoke_sealed_f1_read",
        return_value=(invoked, proof, obs),
    ):
        turn = await try_operational_read_short_circuit_turn(
            message="How is my company doing?",
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state={},
        )
    body = str(turn["message"])
    assert "contractsent" in body
    assert "12,000" in body or "12000" in body
    assert (
        "google analytics" in body.lower()
        or "google_analytics" in body.lower()
        or "search console" in body.lower()
        or "pending" in body.lower()
    )
    assert "win rate" in body.lower()


@pytest.mark.asyncio
async def test_pipeline_follow_up_reuses_operational_read() -> None:
    invoked = NormalizedResult(
        success=True,
        action="hubspot.deals.list",
        connector_id="hubspot",
        data={"results": [{"id": "1", "properties": {"dealname": "Acme", "dealstage": "closedwon"}}]},
    )
    proof = MagicMock(ok=True, error_class=None)
    obs = MagicMock(success=True)
    prior = {
        "execution_plan": {
            "plan_id": "plan-1",
            "capability_id": "sales.pipeline.health",
            "terminal_status": "completed",
            "steps": [{"step_id": "read_sales_pipeline_health", "action_key": "hubspot.deals.list"}],
        },
        "provider_result_evidence": {
            "action_key": "hubspot.deals.list",
            "provider_invoked": True,
            "result_count": 1,
        },
    }
    with patch(
        "app.services.operational_read_execution.invoke_sealed_f1_read",
        return_value=(invoked, proof, obs),
    ) as mock_invoke:
        turn = await try_operational_read_short_circuit_turn(
            message="What appears important?",
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state=prior,
        )
    assert turn is not None
    assert "What appears important:" in str(turn["message"])
    assert mock_invoke.call_args.kwargs["action_key"] == "hubspot.deals.list"


@pytest.mark.asyncio
async def test_stored_deliverable_is_not_reinvoked() -> None:
    prior = {
        "execution_plan": {
            "plan_id": "plan-keep",
            "capability_id": "sales.pipeline.health",
            "terminal_status": "completed",
            "steps": [{"step_id": "read_sales_pipeline_health", "action_key": "hubspot.deals.list"}],
        },
        "provider_result_evidence": {
            "action_key": "hubspot.deals.list",
            "provider_invoked": True,
            "result_count": 2,
        },
        "execution_observations": [
            {
                "step_id": "read_sales_pipeline_health",
                "observation_id": "obs-keep",
                "success": True,
                "summary": "From the connected CRM I received 2 deals in this sample.",
                "structured": {"action_key": "hubspot.deals.list", "result_count": 2, "provider_invoked": True},
            }
        ],
        "durable_deliverable": {
            "diagnosis": "From the connected CRM I received 2 deals in this sample.",
            "evidence": ["hubspot.deals.list rows=2 obs=obs-keep"],
            "required": False,
        },
        "work_artifacts": [
            {
                "artifact_id": "report:plan-keep",
                "kind": "report",
                "title": "Pipeline sample",
                "preview": "2 deals",
                "metadata": {
                    "plan_id": "plan-keep",
                    "outcome": "completed",
                    "observation_ids": ["obs-keep"],
                    "code": "Evidence\n- hubspot.deals.list rows=2 obs=obs-keep",
                },
            }
        ],
    }
    with patch("app.services.operational_read_execution.invoke_sealed_f1_read") as mock_invoke:
        turn = await try_operational_read_short_circuit_turn(
            message="Remind me of that report. Do not create HubSpot records.",
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state=prior,
        )
    assert mock_invoke.call_count == 0
    assert turn["execution_path"] == "operational_f1_read_resume"
    assert turn["execution_result"]["entity_id"] == "plan-keep"
    assert turn["provider_reinvoked"] is False


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
