"""Cancelled durable work must never be revived by late observations."""
from app.services.autonomous_execution_loop import decide_execution_loop
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep


def _plan(status="running"):
    return ExecutionPlan(
        plan_id="cancel-test",
        summary="Send a message",
        steps=[ExecutionStep(step_id="send", title="Send", kind="write", status="pending")],
        source="test",
        terminal_status=status,
    )


def test_cancelled_plan_stops_before_pending_write():
    plan = _plan("cancelled")
    result = decide_execution_loop(plan=plan, task_state={})
    assert result.action == "stop"
    assert result.reason == "cancelled"
    assert result.terminal is True
    assert result.next_step_id is None


def test_cancelled_session_overrides_stale_approval():
    plan = _plan()
    result = decide_execution_loop(
        plan=plan,
        task_state={
            "durable_session": {"phase": "CANCELLED"},
            "pending_action": {"status": "awaiting_approval"},
            "execution_observations": [{"success": True}],
        },
    )
    assert result.action == "stop"
    assert result.reason == "cancelled"
    assert plan.terminal_status == "cancelled"
