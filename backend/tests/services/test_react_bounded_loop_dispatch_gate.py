"""ReAct dispatch must respect bounded-loop cancellation and approval gates."""
import pytest

from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.react_execution_strategy import ReactPlanRuntime


def _runtime(task_state=None, terminal_status="running"):
    plan = ExecutionPlan(
        plan_id="react-gate",
        summary="Check inbox",
        source="test",
        terminal_status=terminal_status,
        steps=[ExecutionStep(step_id="read-1", title="Read inbox", kind="read", status="pending")],
    )
    return ReactPlanRuntime(plan=plan, task_state=task_state or {})


def test_cancelled_plan_cannot_allocate_react_tool_step():
    runtime = _runtime(terminal_status="cancelled")
    with pytest.raises(RuntimeError, match="react_dispatch_blocked:cancelled"):
        runtime.next_step_id("gmail.search", 0)


def test_cancelled_durable_session_cannot_allocate_react_tool_step():
    runtime = _runtime({"durable_session": {"phase": "CANCELLED"}})
    with pytest.raises(RuntimeError, match="react_dispatch_blocked:cancelled"):
        runtime.next_step_id("gmail.search", 0)


def test_pending_approval_blocks_react_tool_allocation():
    runtime = _runtime({"pending_action": {"status": "awaiting_approval"}})
    with pytest.raises(RuntimeError, match="react_dispatch_blocked:approval_required"):
        runtime.next_step_id("gmail.search", 0)


def test_read_step_can_continue_without_approval():
    runtime = _runtime()
    assert runtime.next_step_id("gmail.search", 0) == "read-1"


def test_iteration_budget_blocks_tool_allocation():
    runtime = _runtime()
    with pytest.raises(RuntimeError, match="react_dispatch_blocked:"):
        runtime.next_step_id("gmail.search", 8)


def test_cancelled_late_observation_is_recorded_without_regating_or_resuming():
    from app.services.react_execution_strategy import react_observation_from_tool_call, finalize_react_execution_plan
    runtime = _runtime()
    step = runtime.next_step_id("gmail.search", 0)
    runtime.plan.terminal_status = "cancelled"
    observation = react_observation_from_tool_call(runtime, iteration=0, tool_name="gmail.search",
        observation={"success": True, "action": "gmail.messages.list"})
    assert observation.step_id == step
    assert runtime.plan.terminal_status == "cancelled"
    final, _ = finalize_react_execution_plan(runtime, react_status="completed", answer="old reply")
    assert final.terminal_status == "cancelled"


def test_denied_dispatch_observation_does_not_dispatch_again():
    from app.services.react_execution_strategy import react_observation_from_tool_call
    runtime = _runtime(terminal_status="cancelled")
    observation = react_observation_from_tool_call(runtime, iteration=0, tool_name="gmail.search",
        observation={"success": False, "error_code": "execution_loop_blocked", "error": "cancelled"})
    assert not observation.success
    assert runtime.plan.terminal_status == "cancelled"


def test_verification_policy_cannot_authorize_a_new_write():
    runtime = _runtime()
    runtime.plan.steps = [ExecutionStep("write-1", "Uncertain send", "write", status="failed")]
    with pytest.raises(RuntimeError, match="write_failed_or_uncertain"):
        runtime.next_step_id("gmail.send", 0, is_write=True)


@pytest.mark.parametrize("pending", ["awaiting_admin_approval", "awaiting_step_confirm", "awaiting_plan_confirm"])
def test_all_pending_approval_states_block_dispatch(pending):
    runtime = _runtime({"pending_action": {}, "pending_task": {"status": pending}})
    with pytest.raises(RuntimeError, match="approval_required"):
        runtime.next_step_id("gmail.send", 0, is_write=True)
