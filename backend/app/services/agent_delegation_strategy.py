"""Phase E5.9 — Agent delegation with explicit parent/child plan lineage."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.services.execution_plan_service import ExecutionObservation, ExecutionPlan, ExecutionStep


def execution_plan_with_agent_delegation_step(
    parent: ExecutionPlan,
    *,
    agent_id: str,
    objective: str,
    expected_output: str | None = None,
    context_ref: str | None = None,
) -> ExecutionPlan:
    step_id = f"delegate_{agent_id}_{len(parent.steps)}"
    parent.steps.append(
        ExecutionStep(
            step_id=step_id,
            title=f"Delegate to agent {agent_id}",
            kind="agent_delegation",
            status="pending",
            meta={
                "agent_id": agent_id,
                "objective": objective,
                "expected_output": expected_output,
                "context_ref": context_ref,
            },
        )
    )
    parent.execution_strategy = parent.execution_strategy or "DELEGATED"
    return parent


def create_child_plan_for_delegation(
    parent: ExecutionPlan,
    *,
    parent_step_id: str,
    agent_id: str,
    objective: str,
) -> ExecutionPlan:
    child_id = str(uuid4())
    return ExecutionPlan(
        plan_id=child_id,
        summary=objective,
        objective=objective,
        steps=[
            ExecutionStep(
                step_id=f"agent_{agent_id}_primary",
                title=objective,
                kind="agent_delegation",
                status="pending",
                meta={"agent_id": agent_id},
            )
        ],
        source=f"agent_delegation:{agent_id}",
        execution_strategy="DELEGATED",
        parent_plan_id=parent.plan_id,
        parent_step_id=parent_step_id,
        continuation_of_plan_id=parent.plan_id,
        revision=1,
    )


def delegation_observation(
    *,
    parent_plan_id: str,
    parent_step_id: str,
    child_plan: ExecutionPlan,
    result: dict[str, Any],
    latency_ms: int | None = None,
) -> ExecutionObservation:
    success = not result.get("error")
    from app.services.outcome_verification import evidence_is_verified, outcome_from_tool_calls

    # execution_verified means "a tool ran"; it is never completion proof.
    if isinstance(result.get("tool_calls"), list):
        child_verified = outcome_from_tool_calls(result["tool_calls"]).status == "completed" and (
            result.get("outcome_verified") is not False
        )
    else:
        child_verified = result.get("outcome_verified") is True or evidence_is_verified(result)
    # A delegated agent finishing its computation is not proof that any requested
    # external effect occurred. Parent completion consumes this explicit bit.
    return ExecutionObservation(
        observation_id=str(uuid4()),
        step_id=parent_step_id,
        connector_id=f"agent:{child_plan.plan_id}",
        success=success,
        summary=str(result.get("summary") or result.get("error") or "delegation complete"),
        structured={
            "child_plan_id": child_plan.plan_id,
            "parent_plan_id": parent_plan_id,
            "agent_result": dict(result),
            "child_terminal_status": child_plan.terminal_status,
            "verified": child_verified,
            **(
                {"verification": {"verified": True, "method": "delegated_outcome", "kind": "agent"}}
                if child_verified
                else {}
            ),
        },
        error=str(result.get("error") or "") or None,
        source="agent_delegation",
        plan_id=parent_plan_id,
    )
