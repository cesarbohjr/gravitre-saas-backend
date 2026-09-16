"""Phase E5.8 — Workflow invocation as ExecutionPlan step + observation."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.services.execution_plan_service import ExecutionObservation, ExecutionPlan, ExecutionStep


def execution_plan_step_for_workflow(
    *,
    workflow_id: str,
    workflow_name: str | None = None,
    arguments: dict[str, Any] | None = None,
    plan_id: str | None = None,
    objective: str | None = None,
) -> ExecutionPlan:
    label = workflow_name or workflow_id
    return ExecutionPlan(
        plan_id=plan_id or str(uuid4()),
        summary=objective or f"Execute workflow: {label}",
        objective=objective or f"Execute workflow: {label}",
        steps=[
            ExecutionStep(
                step_id=f"workflow_{workflow_id}",
                title=f"Run workflow {label}",
                kind="workflow",
                action_key="assistant.execute_workflow",
                status="pending",
                meta={
                    "workflow_id": workflow_id,
                    "workflow_name": workflow_name,
                    "arguments": dict(arguments or {}),
                },
            )
        ],
        source="workflow_invocation",
        execution_strategy="WORKFLOW",
    )


def apply_workflow_result_to_plan(
    plan: ExecutionPlan,
    *,
    step_id: str,
    result: dict[str, Any],
    latency_ms: int | None = None,
) -> ExecutionPlan:
    """Workflow graph remains internal; parent step receives canonical terminal."""
    from app.services.execution_plan_service import apply_observations_to_plan

    step = next((s for s in plan.steps if s.step_id == step_id), plan.steps[0] if plan.steps else None)
    if step is None:
        return plan
    obs = workflow_observation(
        plan_id=plan.plan_id,
        step_id=step.step_id,
        workflow_id=str((step.meta or {}).get("workflow_id") or ""),
        result=result,
        latency_ms=latency_ms,
    )
    updated = apply_observations_to_plan(plan, [obs])
    status = str(result.get("status") or "").lower()
    if result.get("error"):
        updated.terminal_status = "failed"
    elif status in {"partial"}:
        updated.terminal_status = "partial"
    elif status in {"blocked"}:
        updated.terminal_status = "blocked"
    elif status in {"completed", "queued", "success"}:
        if updated.terminal_status not in {"failed", "partial"}:
            updated.terminal_status = "completed"
    return updated


def workflow_observation(
    *,
    plan_id: str,
    step_id: str,
    workflow_id: str,
    result: dict[str, Any],
    latency_ms: int | None = None,
) -> ExecutionObservation:
    success = not result.get("error")
    return ExecutionObservation(
        observation_id=str(uuid4()),
        step_id=step_id,
        connector_id="workflow",
        success=success,
        summary=str(result.get("message") or result.get("error") or "workflow executed"),
        structured=dict(result),
        error=str(result.get("error") or "") or None,
        source="workflow",
        resource=workflow_id,
        latency_ms=latency_ms,
        plan_id=plan_id,
    )
