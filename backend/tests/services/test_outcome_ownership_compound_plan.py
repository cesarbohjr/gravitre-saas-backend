from __future__ import annotations

from app.services.execution_plan_service import (
    ExecutionObservation,
    ExecutionPlan,
    ExecutionStep,
    apply_observations_to_plan,
)


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="compound-1",
        summary="Research account, update CRM, and delegate follow-up",
        objective="Deliver a verified multi-system outcome",
        source="test",
        steps=[
            ExecutionStep(step_id="research", title="Research", kind="read"),
            ExecutionStep(step_id="crm", title="Update CRM", kind="write"),
            ExecutionStep(step_id="agent", title="Delegate follow-up", kind="agent_delegation"),
        ],
    )


def test_compound_plan_does_not_complete_on_child_success_without_verification() -> None:
    plan = apply_observations_to_plan(
        _plan(),
        [
            ExecutionObservation("research", "web", True, "found", {"verified": True}),
            ExecutionObservation("crm", "hubspot", True, "accepted", {"id": "1"}),
            ExecutionObservation("agent", "agent", True, "returned output", {}),
        ],
    )
    # Every step ran but two consequential ones lack proof: an honest terminal
    # state, not a perpetual "running" that the stall detector reports as stuck.
    assert plan.terminal_status == "verification_inconclusive"
    assert next(s for s in plan.steps if s.step_id == "crm").status == "running"
    assert next(s for s in plan.steps if s.step_id == "agent").status == "running"


def test_compound_plan_completes_when_all_consequential_children_verified() -> None:
    plan = apply_observations_to_plan(
        _plan(),
        [
            ExecutionObservation("research", "web", True, "found", {"verified": True}),
            ExecutionObservation(
                "crm",
                "hubspot",
                True,
                "read back",
                {"id": "1", "verification": {"verified": True, "method": "entity_get"}},
            ),
            ExecutionObservation(
                "agent",
                "agent",
                True,
                "artifact verified",
                {"verification": {"verified": True, "method": "delegated_outcome"}},
            ),
        ],
    )
    assert plan.terminal_status == "completed"
    assert all(s.status == "completed" for s in plan.steps)


def test_bare_verified_flag_cannot_complete_a_write_step() -> None:
    plan = apply_observations_to_plan(
        _plan(),
        [
            ExecutionObservation("research", "web", True, "found", {}),
            ExecutionObservation("crm", "hubspot", True, "accepted", {"verified": True}),
            ExecutionObservation(
                "agent", "agent", True, "ok", {"verification": {"verified": True, "method": "delegated_outcome"}}
            ),
        ],
    )
    assert plan.terminal_status == "verification_inconclusive"
