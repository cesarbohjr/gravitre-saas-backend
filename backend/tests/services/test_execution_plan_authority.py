"""ECO-013 / DEC-005: stale producers cannot replace terminal write truth."""
from dataclasses import replace

import pytest

from app.services.execution_plan_authority import is_terminal_write_plan, prefer_persisted_write_plan
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.execution_plan_adapters import enrich_task_state_patch


def _terminal(status="cancelled", revision=5):
    return ExecutionPlan(
        plan_id="write-plan", summary="Approved write", source="connector_write",
        terminal_status=status, revision=revision,
        steps=[ExecutionStep(step_id="write", title="Write", kind="write", status="completed")],
    )


@pytest.mark.parametrize("status", ["completed", "partial", "failed", "blocked", "cancelled", "verification_inconclusive"])
@pytest.mark.parametrize("incoming_status", ["pending", "running", "waiting_for_approval", "completed", "failed"])
def test_older_same_plan_revision_cannot_overwrite_terminal_truth(status, incoming_status):
    current = _terminal(status)
    incoming = replace(current, terminal_status=incoming_status, revision=4, turn_id="late-turn")
    assert prefer_persisted_write_plan(current, incoming) is current
    assert current.terminal_status == status
    assert current.revision == 5
    assert current.turn_id is None


def test_inconclusive_write_is_terminal_without_claiming_success():
    current = _terminal("verification_inconclusive")
    assert is_terminal_write_plan(current)
    compose = replace(current, source="default_compose", terminal_status="running", revision=6)
    result = prefer_persisted_write_plan(current, compose)
    assert result is current
    assert result.terminal_status == "verification_inconclusive"


def test_newer_verified_outcome_can_resolve_inconclusive_write():
    current = _terminal("verification_inconclusive")
    verified = replace(current, terminal_status="completed", revision=6)
    assert prefer_persisted_write_plan(current, verified) is verified


def test_distinct_action_can_request_approval_after_previous_action_finishes():
    current = _terminal()
    next_action = replace(current, plan_id="next-write", terminal_status="waiting_for_approval", revision=1)
    assert prefer_persisted_write_plan(current, next_action) is next_action


@pytest.mark.parametrize("incoming_status", ["waiting_for_approval", "completed"])
def test_state_patch_adapter_preserves_newer_cancellation(incoming_status):
    current = _terminal()
    stale = replace(current, terminal_status=incoming_status, revision=4)
    patch = enrich_task_state_patch(
        {"execution_plan": stale.as_dict()},
        current_state={"execution_plan": current.as_dict()},
    )
    assert patch["execution_plan"]["terminal_status"] == "cancelled"
    assert patch["execution_plan"]["revision"] == 5


@pytest.mark.parametrize("legacy_status", ["awaiting_confirm", "awaiting_params", "executing"])
def test_canonical_clarification_cannot_be_projected_as_approval(legacy_status):
    plan = replace(_terminal(), terminal_status="clarification_required", pending_action_id=None)
    patch = enrich_task_state_patch(
        {"pending_task": {"status": legacy_status}},
        current_state={"execution_plan": plan.as_dict()},
    )
    assert patch["pending_task"]["status"] == "awaiting_params"
    assert patch["pending_task"]["execution_plan_id"] == plan.plan_id
