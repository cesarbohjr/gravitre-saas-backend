"""Cancellation is terminal across both observation-policy and plan reconciliation."""
from app.services.execution_plan_service import (
    ExecutionObservation,
    ExecutionPlan,
    ExecutionStep,
    apply_observations_to_plan,
)


def test_late_verified_write_does_not_resurrect_cancelled_plan():
    plan = ExecutionPlan(
        plan_id="cancelled-write",
        summary="Send email",
        source="test",
        terminal_status="cancelled",
        steps=[ExecutionStep(step_id="send", title="Send", kind="write", status="pending")],
    )
    observation = ExecutionObservation(
        step_id="send",
        connector_id="gmail",
        success=True,
        summary="Provider responded after cancellation",
        structured={
            "verified": True,
            "verification_status": "verified",
            "provider_record_id": "late-1",
        },
    )
    result = apply_observations_to_plan(plan, [observation])
    assert result.terminal_status == "cancelled"
    assert result.steps[0].status == "pending"


def test_late_failed_observation_does_not_resurrect_cancelled_plan():
    plan = ExecutionPlan(
        plan_id="cancelled-read",
        summary="Read inbox",
        source="test",
        terminal_status="cancelled",
        steps=[ExecutionStep(step_id="read", title="Read", kind="read", status="pending")],
    )
    observation = ExecutionObservation(
        step_id="read",
        connector_id="gmail",
        success=False,
        summary="Late failure",
    )
    result = apply_observations_to_plan(plan, [observation])
    assert result.terminal_status == "cancelled"
    assert result.steps[0].status == "pending"
