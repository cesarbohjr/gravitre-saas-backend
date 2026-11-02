from unittest.mock import AsyncMock

import pytest

from app.services.cognitive_execution_engine import execute_read_steps_parallel, apply_observations_to_plan
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep, ExecutionObservation


def plan(status="pending"):
    return ExecutionPlan(plan_id="p1", summary="read then write", source="test", terminal_status=status, steps=[ExecutionStep(step_id="r", title="Read", kind="read", connector_id="hubspot"), ExecutionStep(step_id="w", title="Write", kind="write", connector_id="hubspot")])


@pytest.mark.asyncio
async def test_exception_is_a_failed_observation_without_losing_error_scope_or_leaking_details():
    current = plan()
    observations = await execute_read_steps_parallel(current, context={}, handler=AsyncMock(side_effect=RuntimeError("private-token")))
    assert len(observations) == 1 and not observations[0].success
    assert observations[0].error == "read_execution_failed"
    assert "private-token" not in str(observations)
    assert observations[0].plan_id == "p1"


@pytest.mark.asyncio
async def test_reads_do_not_execute_or_complete_pending_write():
    current = plan()
    handler = AsyncMock(return_value=ExecutionObservation(step_id="r", connector_id="hubspot", success=True, summary="Read returned"))
    observations = await execute_read_steps_parallel(current, context={}, handler=handler)
    assert handler.await_count == 1
    updated = apply_observations_to_plan(current, observations)
    assert updated.steps[0].status == "completed" and updated.steps[1].status == "pending"
    assert updated.terminal_status != "completed"


@pytest.mark.asyncio
async def test_cancelled_plan_neither_starts_reads_nor_accepts_late_completion():
    current = plan("cancelled")
    handler = AsyncMock()
    assert await execute_read_steps_parallel(current, context={}, handler=handler) == []
    handler.assert_not_awaited()
    updated = apply_observations_to_plan(current, [ExecutionObservation(step_id="r", connector_id="hubspot", success=True, summary="late")])
    assert updated.terminal_status == "cancelled" and updated.steps[0].status == "pending"


@pytest.mark.asyncio
async def test_other_plan_observations_cannot_complete_this_plan():
    current = plan()
    foreign = ExecutionObservation(step_id="r", connector_id="hubspot", success=True, summary="foreign", plan_id="other")
    result = await execute_read_steps_parallel(current, context={}, handler=AsyncMock(return_value=foreign))
    assert result[0].error == "observation_identity_mismatch"
    apply_observations_to_plan(current, [foreign])
    assert current.steps[0].status == "pending"


@pytest.mark.parametrize("trial", range(20))
def test_twenty_yes_wait_trials_protect_real_final_write_boundary(trial, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.services import voice_pause_gate
    from app.services.spoken_write_approval import classify_spoken_write_approval
    from app.services.tool_types import ToolValidationError
    from app.services.voice_barge_in_write import begin_write_effect

    monkeypatch.setattr("app.services.chat_turn_cancel_service.is_stop_requested", lambda *_a, **_kw: False)
    state = {"pending_task": {"id": "draft", "type": "connector_action", "status": "awaiting_confirm", "invoke_action": "gmail.messages.send"}}
    decision = classify_spoken_write_approval("Yes, wait. Hold on.", task_state=state)
    assert decision.decision == "hold_commit" and not decision.invoke_allowed
    ctx = SimpleNamespace(org_id="phase3-a", conversation_id=f"trial-{trial}", settings=SimpleNamespace())
    provider = MagicMock()
    # Deterministic expiry exercises the real refusal path without waiting
    # the production 30-second hold on each of twenty unit trials. Timing and
    # resume behavior are covered by the existing voice-pause suite.
    voice_pause_gate.pause(ctx.org_id, ctx.conversation_id, max_s=0)
    try:
        with pytest.raises(ToolValidationError):
            begin_write_effect(ctx, "gmail.send")
            provider()
        provider.assert_not_called()
    finally:
        voice_pause_gate.end_pause(ctx.org_id, ctx.conversation_id)
