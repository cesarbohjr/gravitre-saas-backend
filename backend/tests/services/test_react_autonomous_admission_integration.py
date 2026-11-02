"""Explicit autonomous ReAct dispatch must fail closed before allocating tools."""
import pytest

from app.services.autonomous_task_contract import AutonomousStep, AutonomousTask
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.react_execution_strategy import ReactPlanRuntime


def _runtime(kind="read"):
    plan = ExecutionPlan(
        plan_id="autonomous-gate", summary="Run task", source="test",
        terminal_status="running",
        steps=[ExecutionStep("step-1", "Do action", kind, status="pending")],
    )
    task = AutonomousTask(
        "task-1", "tenant-1", "actor-1", "Run task",
        (AutonomousStep("step-1", "crm.search" if kind == "read" else "crm.update",
                        kind, idempotency_key="task-1:step-1" if kind == "write" else None),),
    )
    return ReactPlanRuntime(plan=plan, autonomous_task=task)


def test_opt_in_read_requires_fresh_authorization_and_matching_scope():
    runtime = _runtime()
    with pytest.raises(RuntimeError, match="permission_denied"):
        runtime.next_step_id("crm.search", 0, tenant_id="tenant-1", actor_id="actor-1")
    assert not runtime.dispatched_steps
    assert runtime.next_step_id("crm.search", 0, tenant_id="tenant-1",
                                actor_id="actor-1", fresh_permission_granted=True) == "step-1"


@pytest.mark.parametrize("kwargs,reason", [
    ({}, "task_scope_mismatch"),
    ({"tenant_id": "other", "actor_id": "actor-1"}, "task_scope_mismatch"),
    ({"tenant_id": "tenant-1", "actor_id": "actor-1",
      "fresh_permission_granted": True}, "approval_not_granted"),
    ({"tenant_id": "tenant-1", "actor_id": "actor-1",
      "fresh_permission_granted": True, "fresh_approval_granted": True}, None),
])
def test_write_dispatch_requires_fresh_approval(kwargs, reason):
    runtime = _runtime("write")
    if reason:
        with pytest.raises(RuntimeError, match=reason):
            runtime.next_step_id("crm.update", 0, is_write=True, **kwargs)
        assert not runtime.dispatched_steps
    else:
        assert runtime.next_step_id("crm.update", 0, is_write=True, **kwargs) == "step-1"


def test_autonomous_runtime_rejects_unplanned_dynamic_tools():
    runtime = _runtime()
    runtime.plan.steps.clear()
    with pytest.raises(RuntimeError, match="unplanned_autonomous_step"):
        runtime.next_step_id("crm.search", 0)
