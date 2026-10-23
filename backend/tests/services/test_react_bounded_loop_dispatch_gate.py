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
