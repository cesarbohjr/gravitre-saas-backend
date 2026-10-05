from __future__ import annotations

from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.react_execution_strategy import ReactPlanRuntime, finalize_react_execution_plan


def test_react_answer_cannot_complete_write_without_observation() -> None:
    runtime = ReactPlanRuntime(
        plan=ExecutionPlan(
            plan_id="p1",
            summary="Create CRM record",
            source="test",
            steps=[ExecutionStep(step_id="w", title="Create", kind="write")],
        )
    )
    plan, _ = finalize_react_execution_plan(runtime, react_status="done", answer="Done")
    assert plan.terminal_status == "verification_inconclusive"


def test_react_provider_success_without_verified_evidence_is_inconclusive() -> None:
    runtime = ReactPlanRuntime(
        plan=ExecutionPlan(
            plan_id="p2",
            summary="Create CRM record",
            source="test",
            steps=[ExecutionStep(step_id="w", title="Create", kind="write")],
        )
    )
    runtime.record_tool_observation(
        step_id="w",
        tool_name="hubspot",
        observation={"success": True, "id": "123"},
    )
    plan, _ = finalize_react_execution_plan(runtime, react_status="done")
    assert plan.terminal_status == "verification_inconclusive"


def test_react_verified_write_can_complete() -> None:
    runtime = ReactPlanRuntime(
        plan=ExecutionPlan(
            plan_id="p3",
            summary="Create CRM record",
            source="test",
            steps=[ExecutionStep(step_id="w", title="Create", kind="write")],
        )
    )
    runtime.record_tool_observation(
        step_id="w",
        tool_name="hubspot",
        observation={"success": True, "verified": True, "id": "123"},
    )
    plan, _ = finalize_react_execution_plan(runtime, react_status="done")
    assert plan.terminal_status == "completed"
