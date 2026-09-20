"""Canonical ExecutionStep dispatch boundary (E5 plan-first).

All cognitive runtime side effects must resolve:
    plan_id + step_id + ExecutionStep
→ strategy adapter (DIRECT / PARALLEL / REACT / WORKFLOW / DELEGATED)
→ observation back onto the same plan.

Legacy pending_task may be adapted INTO an ExecutionPlan (ingress).
Once a plan exists, pending_task cannot override connector, action, args,
capability, resource, or objective.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.core.safe_dict import safe_normalize_stored_dict
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep


class StrategicPlanNotExecutable(ValueError):
    """Raised when a non-executable reasoning plan is sent to a dispatcher."""


class CanonicalDispatchError(ValueError):
    """Raised when dispatch cannot identify plan_id + step_id."""


@dataclass(frozen=True)
class DispatchTarget:
    plan_id: str
    step_id: str
    revision: int
    step: ExecutionStep
    plan: ExecutionPlan
    strategy: str


def assert_plan_is_dispatchable(plan: dict[str, Any] | ExecutionPlan | None) -> None:
    """Refuse strategic_reasoning / executable=false at the dispatch boundary."""
    if plan is None:
        return
    if isinstance(plan, ExecutionPlan):
        return
    if not isinstance(plan, dict):
        return
    if plan.get("executable") is False:
        raise StrategicPlanNotExecutable(
            "strategic_reasoning plans are not executable; use ExecutionPlan"
        )
    kind = str(plan.get("plan_kind") or "").strip().lower()
    if kind in {"strategic", "strategic_reasoning"}:
        raise StrategicPlanNotExecutable(
            "strategic_reasoning plans are not executable; use ExecutionPlan"
        )


def _executable_steps(plan: ExecutionPlan) -> list[ExecutionStep]:
    return [
        s
        for s in plan.steps
        if s.kind in {"read", "write", "workflow", "agent_delegation", "clarify"}
        and s.status not in {"completed", "skipped"}
    ]


def resolve_dispatch_target(
    task_state: dict[str, Any] | None,
    *,
    step_id: str | None = None,
) -> DispatchTarget | None:
    """Resolve the canonical step to execute. ExecutionPlan is authoritative."""
    state = task_state if isinstance(task_state, dict) else {}
    plan = ExecutionPlan.from_dict(state.get("execution_plan"))
    if plan is None:
        return None
    assert_plan_is_dispatchable(plan)
    steps = plan.steps
    chosen: ExecutionStep | None = None
    if step_id:
        chosen = next((s for s in steps if s.step_id == step_id), None)
    if chosen is None:
        pending = _executable_steps(plan)
        chosen = pending[0] if pending else (steps[0] if steps else None)
    if chosen is None:
        return None
    strategy = str(plan.execution_strategy or chosen.kind or "DIRECT").upper()
    if chosen.kind == "workflow":
        strategy = "WORKFLOW"
    elif chosen.kind == "agent_delegation":
        strategy = "DELEGATED"
    return DispatchTarget(
        plan_id=plan.plan_id,
        step_id=chosen.step_id,
        revision=int(plan.revision or 1),
        step=chosen,
        plan=plan,
        strategy=strategy,
    )


def connector_plan_from_execution_step(step: ExecutionStep) -> ConnectorActionPlan | None:
    """One-way adapter: ExecutionStep → ConnectorActionPlan (RUNTIME_INTERNAL)."""
    meta = dict(step.meta or {})
    invoke = str(step.action_key or meta.get("invoke_action") or "").strip()
    integration = str(step.connector_id or meta.get("integration") or "").strip()
    if not invoke and not integration:
        return None
    args = meta.get("args") if isinstance(meta.get("args"), dict) else {}
    kind = "write" if step.kind == "write" else str(meta.get("kind") or step.kind or "read")
    return ConnectorActionPlan(
        tool_name=str(meta.get("tool_name") or invoke.replace(".", "_") or ""),
        invoke_action=invoke,
        integration=integration or "connector",
        kind=kind,
        label=str(step.title or meta.get("label") or invoke),
        args=dict(args),
        requires_approval=bool(meta.get("requires_approval")),
        approval_reason=meta.get("approval_reason"),
        destructive=bool(meta.get("destructive")),
        inferred_fields=tuple(str(x) for x in (meta.get("inferred_fields") or ())),
        inference_sources=safe_normalize_stored_dict(meta.get("inference_sources")),
    )


def stamp_step_from_connector_plan(step: ExecutionStep, plan: ConnectorActionPlan) -> ExecutionStep:
    """Persist frozen connector payload onto the canonical step (one-way)."""
    return ExecutionStep(
        step_id=step.step_id,
        title=step.title or plan.label,
        kind="write" if plan.kind == "write" else step.kind,
        connector_id=plan.integration,
        capability_id=step.capability_id,
        action_key=plan.invoke_action,
        status=step.status,
        meta={
            **step.meta,
            "tool_name": plan.tool_name,
            "invoke_action": plan.invoke_action,
            "integration": plan.integration,
            "args": dict(plan.args),
            "requires_approval": plan.requires_approval,
            "approval_reason": plan.approval_reason,
            "destructive": plan.destructive,
            "inferred_fields": list(plan.inferred_fields),
            "inference_sources": dict(plan.inference_sources),
        },
    )


def ignore_stale_pending_overrides(
    canonical: ConnectorActionPlan,
    pending: dict[str, Any] | None,
) -> ConnectorActionPlan:
    """pending_task may not change connector/action/args/resource once a plan exists."""
    if not isinstance(pending, dict):
        return canonical
    params = pending.get("params") if isinstance(pending.get("params"), dict) else pending
    if not isinstance(params, dict):
        return canonical
    mutated_integration = str(params.get("integration") or params.get("connector_id") or "")
    mutated_action = str(params.get("invoke_action") or params.get("action") or "")
    mutated_args = params.get("args") if isinstance(params.get("args"), dict) else None
    if mutated_integration and mutated_integration != canonical.integration:
        return canonical
    if mutated_action and mutated_action != canonical.invoke_action:
        return canonical
    if mutated_args is not None and dict(mutated_args) != dict(canonical.args):
        return canonical
    return canonical


def resolve_executable_connector_plan(
    task_state: dict[str, Any] | None,
    *,
    structured_plan: ConnectorActionPlan | None = None,
    step_id: str | None = None,
) -> ConnectorActionPlan | None:
    """Plan-first resolver used by write gates and orchestration.

    If ExecutionPlan exists, ConnectorActionPlan is derived from the step.
    Stale pending_task mutations are ignored for execution identity.
    """
    state = task_state if isinstance(task_state, dict) else {}
    current_plan = state.get("current_plan")
    if isinstance(current_plan, dict):
        try:
            assert_plan_is_dispatchable(current_plan)
        except StrategicPlanNotExecutable:
            current_plan = None
    kernel_plan = state.get("ctx_plan") or state.get("_cognitive_ctx_plan")
    if isinstance(kernel_plan, dict):
        assert_plan_is_dispatchable(kernel_plan)

    target = resolve_dispatch_target(state, step_id=step_id)
    if target is not None:
        derived = connector_plan_from_execution_step(target.step)
        if derived is not None and (derived.invoke_action or derived.integration):
            pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else None
            return ignore_stale_pending_overrides(derived, pending)
        if structured_plan is not None:
            return structured_plan
        return derived

    return structured_plan


def dispatch_execution_step(
    *,
    plan_id: str,
    step_id: str,
    step: ExecutionStep,
    execution_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Canonical dispatch envelope — strategies execute this identified step."""
    if not plan_id or not step_id:
        raise CanonicalDispatchError("dispatch requires plan_id and step_id")
    ctx = dict(execution_context or {})
    strategy = str(ctx.get("strategy") or step.kind or "DIRECT").upper()
    return {
        "plan_id": plan_id,
        "step_id": step_id,
        "strategy": strategy,
        "kind": step.kind,
        "connector_id": step.connector_id,
        "action_key": step.action_key,
        "arguments": safe_normalize_stored_dict((step.meta or {}).get("args")),
        "capability_id": step.capability_id,
        "attribution": {"plan_id": plan_id, "step_id": step_id},
    }


def attribute_observation(
    payload: dict[str, Any],
    *,
    plan_id: str,
    step_id: str,
) -> dict[str, Any]:
    return {**payload, "plan_id": plan_id, "step_id": step_id}


def apply_child_result_to_parent(
    parent: ExecutionPlan,
    *,
    parent_step_id: str,
    child: ExecutionPlan,
    observation_structured: dict[str, Any],
) -> ExecutionPlan:
    """Child plans cannot mutate parent steps except via observation on parent_step_id."""
    from app.services.execution_plan_service import ExecutionObservation, apply_observations_to_plan

    if child.parent_plan_id and child.parent_plan_id != parent.plan_id:
        raise CanonicalDispatchError("child plan parent_plan_id does not match parent")
    obs = ExecutionObservation(
        observation_id=str(uuid4()),
        step_id=parent_step_id,
        connector_id=f"agent:{child.plan_id}",
        success=child.terminal_status in {"completed", "partial"} or not observation_structured.get("error"),
        summary=str(observation_structured.get("summary") or child.terminal_status),
        structured={
            **observation_structured,
            "child_plan_id": child.plan_id,
            "parent_plan_id": parent.plan_id,
            "parent_step_id": parent_step_id,
        },
        plan_id=parent.plan_id,
        source="agent_delegation",
    )
    return apply_observations_to_plan(parent, [obs])
