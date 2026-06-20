"""STA-119: Multi-agent swarm coordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.swarm_coordinator_service import (
    SwarmCoordinatorError,
    SwarmSubtaskSpec,
    _options_from_subtask_results,
    _swarm_execution_verified,
    _swarm_run_execution_verified,
    aggregate_swarm_run,
    cancel_swarm_run,
    run_swarm_subtask_job,
    start_swarm,
)


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[])
    mock.insert.return_value = insert_mock

    update_mock = MagicMock()
    update_mock.eq.return_value = update_mock
    update_mock.execute.return_value = MagicMock(data=[])
    mock.update.return_value = update_mock

    return mock


@patch("app.services.swarm_coordinator_service.get_agent")
@pytest.mark.asyncio
async def test_start_swarm_requires_subtasks(mock_get_agent):
    mock_get_agent.return_value = {"id": "parent", "name": "Lead"}
    client = MagicMock()
    with pytest.raises(SwarmCoordinatorError, match="At least one subtask"):
        await start_swarm(
            client,
            org_id="org-1",
            parent_agent_id="parent",
            objective="Evaluate vendor",
            subtasks=[],
            actor_id="user-1",
        )


@patch("app.workers.queue.enqueue_agent_execution_job", new_callable=AsyncMock)
@patch("app.operators.agent_jobs.create_job")
@patch("app.services.swarm_coordinator_service.write_audit_event")
@patch("app.services.swarm_coordinator_service.get_agent")
@pytest.mark.asyncio
async def test_start_swarm_creates_jobs(mock_get_agent, mock_audit, mock_create_job, mock_enqueue):
    mock_get_agent.return_value = {"id": "agent-1", "name": "Analyst", "role": "analyst", "config": {}}
    mock_create_job.return_value = {"id": "job-1"}

    swarm_row = {
        "id": "swarm-1",
        "org_id": "org-1",
        "parent_agent_id": "parent",
        "objective": "Evaluate vendor",
        "status": "running",
        "decision_method": "majority_vote",
        "created_at": "2026-06-08T00:00:00+00:00",
        "updated_at": "2026-06-08T00:00:00+00:00",
    }
    subtask_row = {
        "id": "sub-1",
        "swarm_run_id": "swarm-1",
        "org_id": "org-1",
        "agent_id": "agent-1",
        "task_prompt": "Check pricing",
        "scoped_tools": [{"connectorType": "hubspot", "action": "search_contacts"}],
        "sort_order": 0,
        "status": "queued",
        "created_at": "2026-06-08T00:00:00+00:00",
    }
    runs = _table([])
    runs.insert.return_value.execute.return_value = MagicMock(data=[swarm_row])
    subtasks = _table([])
    subtasks.insert.return_value.execute.return_value = MagicMock(data=[subtask_row])
    subtasks.update.return_value.execute.return_value = MagicMock(
        data=[{**subtask_row, "agent_job_id": "job-1"}]
    )

    client = MagicMock()

    def table(name):
        if name == "agent_swarm_runs":
            return runs
        if name == "agent_swarm_subtasks":
            return subtasks
        return _table([])

    client.table.side_effect = table

    result = await start_swarm(
        client,
        org_id="org-1",
        parent_agent_id="parent",
        objective="Evaluate vendor",
        subtasks=[
            SwarmSubtaskSpec(
                agentId="agent-1",
                task="Check pricing",
                scopedTools=[{"connectorType": "hubspot", "action": "search_contacts"}],
            )
        ],
        actor_id="user-1",
    )

    assert result["status"] == "running"
    assert len(result["subtasks"]) == 1
    assert result["subtasks"][0]["agentJobId"] == "job-1"
    mock_audit.assert_called_once()


def test_options_from_subtask_results():
    subtasks = [
        {
            "sort_order": 0,
            "task_prompt": "Check pricing",
            "result": {"recommendedAction": "approve vendor", "summary": "Looks good"},
        },
        {
            "sort_order": 1,
            "task_prompt": "Check legal",
            "result": {"summary": "Needs review"},
        },
    ]
    options = _options_from_subtask_results(subtasks)
    assert options[0] == "approve vendor"
    assert "Needs review" in options[1]


@patch("app.services.swarm_coordinator_service.get_council_service")
@patch("app.services.swarm_coordinator_service.write_audit_event")
@pytest.mark.asyncio
async def test_aggregate_swarm_run_uses_council(mock_audit, mock_get_council):
    swarm = {
        "id": "swarm-1",
        "org_id": "org-1",
        "objective": "Pick vendor",
        "status": "running",
        "decision_method": "majority_vote",
        "created_by": "user-1",
    }
    subtasks = [
        {
            "id": "sub-1",
            "swarm_run_id": "swarm-1",
            "agent_id": "agent-1",
            "task_prompt": "Pricing",
            "status": "completed",
            "sort_order": 0,
            "result": {"recommendedAction": "approve", "summary": "Good pricing"},
        }
    ]
    runs = _table([swarm])
    runs.update.return_value.execute.return_value = MagicMock(
        data=[
            {
                **swarm,
                "status": "completed",
                "final_recommendation": "approve",
                "final_confidence": 0.9,
                "aggregate_result": {},
            }
        ]
    )
    subtasks_table = _table(subtasks)

    council = MagicMock()
    mock_session = MagicMock()
    mock_session.id = "council-1"
    mock_session.final_recommendation = "approve"
    mock_session.final_confidence = 0.9
    mock_session.dissenting_opinions = []
    mock_session.debate_rounds = []
    council.start_council = AsyncMock(return_value=mock_session)
    mock_get_council.return_value = council

    client = MagicMock()
    client.table.side_effect = lambda name: runs if name == "agent_swarm_runs" else subtasks_table

    with patch("app.services.swarm_coordinator_service.get_agent", return_value={"name": "A", "role": "analyst"}):
        result = await aggregate_swarm_run(client, "org-1", "swarm-1")

    assert result["status"] == "completed"
    assert result["finalRecommendation"] == "approve"
    council.start_council.assert_awaited_once()
    mock_audit.assert_called_once()


@patch("app.services.agent_interrupt_service.request_interrupt")
@patch("app.services.swarm_coordinator_service.write_audit_event")
def test_cancel_swarm_run(mock_audit, mock_interrupt):
    swarm = {
        "id": "swarm-1",
        "org_id": "org-1",
        "status": "running",
        "objective": "Test",
        "decision_method": "majority_vote",
        "created_at": "2026-06-08T00:00:00+00:00",
        "updated_at": "2026-06-08T00:00:00+00:00",
    }
    subtasks = [
        {
            "id": "sub-1",
            "swarm_run_id": "swarm-1",
            "agent_id": "agent-1",
            "task_prompt": "Do work",
            "status": "queued",
            "agent_job_id": "job-1",
            "sort_order": 0,
            "scoped_tools": [],
        }
    ]
    runs = _table([swarm])
    cancelled_swarm = {**swarm, "status": "cancelled", "completed_at": "2026-06-08T01:00:00+00:00"}
    runs.execute.side_effect = [
        MagicMock(data=[swarm]),
        MagicMock(data=[cancelled_swarm]),
    ]
    runs.update.return_value.execute.return_value = MagicMock(data=[cancelled_swarm])
    subtasks_table = _table(subtasks)
    subtasks_table.update.return_value.execute.return_value = MagicMock(data=[{**subtasks[0], "status": "cancelled"}])

    client = MagicMock()
    client.table.side_effect = lambda name: runs if name == "agent_swarm_runs" else subtasks_table

    result = cancel_swarm_run(client, "org-1", "swarm-1", "user-1")
    assert result["status"] == "cancelled"
    mock_interrupt.assert_called_once()
    mock_audit.assert_called_once()


def test_swarm_execution_verified_requires_successful_tool_calls():
    scoped = [{"connectorType": "hubspot", "action": "search_contacts"}]
    assert _swarm_execution_verified(scoped, []) is False
    assert _swarm_execution_verified(scoped, [{"result": {"success": True}}]) is True
    assert _swarm_execution_verified([], [{"result": {"success": True}}]) is False


def test_swarm_run_execution_verified_all_scoped_subtasks():
    subtasks = [
        {"scoped_tools": [{"connectorType": "hubspot"}], "execution_verified": True},
        {"scoped_tools": [], "execution_verified": False},
        {"scoped_tools": [{"connectorType": "slack"}], "execution_verified": True},
    ]
    assert _swarm_run_execution_verified(subtasks) is True
    subtasks[2]["execution_verified"] = False
    assert _swarm_run_execution_verified(subtasks) is False


@patch("app.operators.agent_intelligence.AgentIntelligence")
@patch("app.operators.agent_intelligence.resolve_agent_record")
@patch("app.workflows.repository.get_supabase_client")
@pytest.mark.asyncio
async def test_run_swarm_subtask_job_uses_execution_core(mock_client, mock_resolve, mock_intel_cls):
    mock_client.return_value = MagicMock()
    mock_resolve.return_value = {"id": "agent-1", "name": "Analyst"}
    agent_result = MagicMock()
    agent_result.summary = "Pricing looks competitive"
    agent_result.answer = "Vendor pricing is within budget"
    agent_result.recommended_actions = ["approve vendor"]
    agent_result.confidence = 82
    agent_result.tool_calls = [{"tool": "hubspot_search_contacts", "result": {"success": True}}]
    agent_result.react_status = "completed"
    agent_result.execution_verified = True
    agent_result.execution_mode = "tools_executed"
    agent_result.tool_call_count = 1
    agent_result.tools_available = 1
    mock_intel_cls.return_value.execute_task = AsyncMock(return_value=agent_result)

    job = {
        "id": "job-1",
        "org_id": "org-1",
        "created_by": "user-1",
        "payload": {
            "agentId": "agent-1",
            "task": "Check pricing",
            "objective": "Evaluate vendor",
            "scopedTools": [{"connectorType": "hubspot", "action": "search_contacts"}],
            "subtaskId": "sub-1",
            "swarmRunId": "swarm-1",
        },
    }

    result = await run_swarm_subtask_job(MagicMock(), job)

    assert result["executionVerified"] is True
    assert result["executionMode"] == "tools_executed"
    assert result["toolCallCount"] == 1
    assert result["recommendedAction"] == "approve vendor"
    mock_intel_cls.return_value.execute_task.assert_awaited_once()
    call_kwargs = mock_intel_cls.return_value.execute_task.await_args.kwargs
    assert call_kwargs["parameters"]["surface"] == "swarm"
    assert call_kwargs["parameters"]["subtask_spec"]["scopedTools"][0]["connectorType"] == "hubspot"
