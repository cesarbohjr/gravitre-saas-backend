"""Tests for CoordinationLayer prototype (STA-270)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from typing import Any

import pytest

from app.config import Settings
from app.coordination import (
    CouncilAggregate,
    ParallelFanout,
    SequentialContext,
    is_coordination_layer_enabled,
)
from app.coordination.flags import parse_allowed_org_ids
from app.services.swarm_coordinator_service import SwarmSubtaskSpec


TEST_ORG = "00000000-0000-0000-0000-000000000001"
OTHER_ORG = "11111111-1111-4111-8111-111111111111"


def _settings(**overrides) -> Settings:
    base = {
        "supabase_url": "https://example.supabase.co",
        "supabase_anon_key": "anon",
        "supabase_service_role_key": "service",
        "supabase_jwt_secret": "secret",
    }
    base.update(overrides)
    return Settings(**base)


def test_flag_off_by_default():
    settings = _settings()
    assert is_coordination_layer_enabled(settings, TEST_ORG) is False
    assert is_coordination_layer_enabled(settings, OTHER_ORG) is False


def test_flag_on_only_for_allowed_org():
    settings = _settings(coordination_layer_enabled=True)
    assert is_coordination_layer_enabled(settings, TEST_ORG) is True
    assert is_coordination_layer_enabled(settings, OTHER_ORG) is False


def test_parse_allowed_org_ids():
    parsed = parse_allowed_org_ids(f"{TEST_ORG},{OTHER_ORG}")
    assert TEST_ORG in parsed
    assert OTHER_ORG in parsed


def test_sequential_context_briefing_includes_channel():
    ctx = SequentialContext(
        run_id="run-1",
        step_outputs={"step_a": {"summary": "Qualified lead", "confidence": 0.8}},
        parameters={"objective": "Evaluate lead"},
        current_step_id="step_b",
    )
    briefing = ctx.to_briefing(source_output={"summary": "Handoff"})
    assert "coordination_channel" in briefing
    assert briefing["coordination_channel"]["runId"] == "run-1"
    assert briefing["coordination_channel"]["priorSteps"][0]["stepId"] == "step_a"


def test_sequential_context_from_job_payload():
    payload = {
        "swarmRunId": "swarm-1",
        "coordinationContext": {
            "channel": {
                "runId": "run-1",
                "priorSteps": [{"stepId": "s1", "summary": "done"}],
            }
        },
    }
    ctx = SequentialContext.from_job_payload(payload)
    assert ctx is not None
    assert ctx.run_id == "run-1"
    assert "s1" in ctx.step_outputs


def test_council_aggregate_marks_shared_context():
    aggregate = CouncilAggregate()
    evidence = aggregate.build_workflow_evidence(
        parameters={"x": 1},
        step_outputs={"s1": {"summary": "ok"}},
        source_output={"confidence": 0.5},
        shared_context={"runId": "run-1"},
    )
    assert evidence["coordination_layer"] is True
    assert evidence["shared_context"]["runId"] == "run-1"


@pytest.mark.asyncio
async def test_parallel_fanout_runs_enqueue_callbacks():
    fanout = ParallelFanout()
    calls: list[str] = []

    items: list[tuple[str, Any]] = []
    for idx in range(3):
        job_id = f"job-{idx}"

        async def _enqueue(jid: str = job_id) -> None:
            calls.append(jid)

        items.append((job_id, _enqueue))

    await fanout.fanout(items)
    assert sorted(calls) == ["job-0", "job-1", "job-2"]


@pytest.mark.asyncio
@patch("app.workers.queue.enqueue_agent_execution_job", new_callable=AsyncMock)
@patch("app.operators.agent_jobs.create_job")
@patch("app.services.swarm_coordinator_service.write_audit_event")
@patch("app.services.swarm_coordinator_service.get_agent")
async def test_start_swarm_uses_parallel_fanout_when_flag_on(
    mock_get_agent,
    mock_audit,
    mock_create_job,
    mock_enqueue,
):
    from app.services.swarm_coordinator_service import start_swarm

    mock_get_agent.return_value = {"id": "agent-1", "name": "Agent"}
    mock_create_job.side_effect = lambda *args, **kwargs: {"id": f"job-{mock_create_job.call_count}"}

    subtask_insert = MagicMock()
    subtask_insert.data = [{"id": "sub-1", "swarm_run_id": "swarm-1", "agent_id": "agent-1", "task_prompt": "t", "status": "queued"}]
    subtask_update = MagicMock()
    subtask_update.data = [{**subtask_insert.data[0], "agent_job_id": "job-1"}]

    swarm_insert = MagicMock()
    swarm_insert.data = [{"id": "swarm-1", "org_id": TEST_ORG, "objective": "obj", "status": "running", "decision_method": "majority_vote"}]

    client = MagicMock()
    client.table.return_value.insert.return_value.execute.side_effect = [swarm_insert, subtask_insert]
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = subtask_update

    settings = _settings(coordination_layer_enabled=True)
    result = await start_swarm(
        client,
        org_id=TEST_ORG,
        parent_agent_id="parent",
        objective="Evaluate vendor",
        subtasks=[SwarmSubtaskSpec(agentId="agent-1", task="Check pricing", scopedTools=[])],
        actor_id="user-1",
        settings=settings,
    )

    assert result["status"] == "running"
    mock_enqueue.assert_awaited_once()
    payload = mock_create_job.call_args.kwargs["payload"]
    assert "coordinationContext" in payload
    assert payload["coordinationContext"]["scheduler"] == "parallel_fanout"
