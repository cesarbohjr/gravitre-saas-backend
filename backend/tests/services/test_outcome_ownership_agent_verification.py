from app.services.agent_delegation_strategy import delegation_observation
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.swarm_coordinator_service import _swarm_execution_verified


def _child() -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="child",
        summary="Do external work",
        source="agent_delegation:a",
        terminal_status="completed",
        steps=[ExecutionStep(step_id="c", title="work", kind="agent_delegation", status="completed")],
    )


def test_agent_child_completed_status_is_not_parent_verification() -> None:
    obs = delegation_observation(
        parent_plan_id="parent",
        parent_step_id="delegate",
        child_plan=_child(),
        result={"summary": "done"},
    )
    assert obs.success is True
    assert obs.structured["verified"] is False


def test_agent_child_explicit_verification_propagates() -> None:
    obs = delegation_observation(
        parent_plan_id="parent",
        parent_step_id="delegate",
        child_plan=_child(),
        result={"summary": "done", "verification": {"verified": True}},
    )
    assert obs.structured["verified"] is True


def test_swarm_provider_success_alone_is_not_execution_verified() -> None:
    assert _swarm_execution_verified(
        [{"name": "hubspot"}],
        [{"result": {"success": True, "id": "123"}}],
    ) is False


def test_swarm_requires_explicit_verification_contract() -> None:
    assert _swarm_execution_verified(
        [{"name": "hubspot"}],
        [{"result": {"success": True, "verification": {"verified": True}}}],
    ) is True
