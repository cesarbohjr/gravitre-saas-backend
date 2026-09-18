"""Phase E5.6 — ReAct as execution strategy beneath canonical ExecutionPlan."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.services.execution_plan_service import (
    ExecutionObservation,
    ExecutionPlan,
    ExecutionStep,
    apply_observations_to_plan,
    mark_plan_terminal,
    reconcile_execution_plan,
    replan_execution_plan,
)


from app.services.f2_read_repair import RepairBudget


@dataclass
class ReactPlanRuntime:
    plan: ExecutionPlan
    observations: list[ExecutionObservation] = field(default_factory=list)
    step_index: int = 0
    repair_budget: RepairBudget = field(default_factory=RepairBudget.fresh)

    def next_step_id(self, tool_name: str, iteration: int) -> str:
        pending = [
            s
            for s in self.plan.steps
            if s.kind in {"read", "write", "clarify", "compose", "workflow", "agent_delegation"}
            and s.status == "pending"
        ]
        if pending:
            return pending[0].step_id
        step_id = f"react_{iteration}_{tool_name}"
        self.plan.steps.append(
            ExecutionStep(
                step_id=step_id,
                title=f"ReAct: {tool_name.replace('_', ' ')}",
                kind="read",
                action_key=tool_name,
                status="pending",
                meta={"react_iteration": iteration, "dynamic": True},
            )
        )
        return step_id

    def record_tool_observation(
        self,
        *,
        step_id: str,
        tool_name: str,
        observation: dict[str, Any],
        elapsed_ms: int | None = None,
    ) -> ExecutionObservation:
        success = bool(observation.get("success", True)) and not observation.get("error")
        obs = ExecutionObservation(
            observation_id=str(uuid4()),
            step_id=step_id,
            connector_id=str(observation.get("integration") or tool_name),
            success=success,
            summary=str(observation.get("error") or observation.get("message") or "ok")[:500],
            structured=dict(observation),
            error=str(observation.get("error") or "") or None,
            source="react",
            capability_id=self.plan.capability_id,
            resource=str(observation.get("action") or tool_name),
            latency_ms=elapsed_ms,
            plan_id=self.plan.plan_id,
        )
        self.observations.append(obs)
        self.plan = apply_observations_to_plan(self.plan, self.observations)
        return obs


def prepare_react_execution_plan(
    *,
    message: str,
    task_state: dict[str, Any] | None,
    capability_id: str | None = None,
    connected_integrations: list[str] | None = None,
    turn_id: str | None = None,
    conversation_id: str | None = None,
) -> ReactPlanRuntime:
    plan = reconcile_execution_plan(
        message=message,
        task_state=task_state,
        capability_id=capability_id,
        connected_integrations=connected_integrations,
        turn_id=turn_id,
        conversation_id=conversation_id,
    )
    if not plan.execution_strategy or plan.execution_strategy in {"ANSWER_ONLY", "DIRECT"}:
        plan.execution_strategy = "REACT"
    if plan.terminal_status == "pending":
        plan.terminal_status = "running"
    if not plan.steps or all(s.kind == "compose" for s in plan.steps):
        plan.steps = [
            ExecutionStep(
                step_id="react_compose",
                title="ReAct reasoning loop",
                kind="compose",
                status="running",
                meta={"strategy": "REACT"},
            )
        ]
    return ReactPlanRuntime(plan=plan)


def react_observation_from_tool_call(
    runtime: ReactPlanRuntime,
    *,
    iteration: int,
    tool_name: str,
    observation: dict[str, Any],
    elapsed_ms: int | None = None,
) -> ExecutionObservation:
    step_id = runtime.next_step_id(tool_name, iteration)
    return runtime.record_tool_observation(
        step_id=step_id,
        tool_name=tool_name,
        observation=observation,
        elapsed_ms=elapsed_ms,
    )


def finalize_react_execution_plan(
    runtime: ReactPlanRuntime,
    *,
    react_status: str,
    answer: str = "",
    force_replan: bool = False,
    replan_reason: str | None = None,
) -> tuple[ExecutionPlan, list[ExecutionObservation]]:
    plan = runtime.plan
    status = str(react_status or "").lower()
    if force_replan and replan_reason:
        remaining = [s for s in plan.steps if s.status == "pending"]
        plan = replan_execution_plan(plan, new_steps=remaining or plan.steps, reason=replan_reason)
        plan.execution_strategy = "REACT"
        return plan, runtime.observations

    if status in {"needs_human_input", "needs_human"}:
        plan = mark_plan_terminal(plan, "clarification_required")
    elif status in {"error"}:
        plan = mark_plan_terminal(plan, "failed")
    elif status in {"max_iterations_reached"}:
        if runtime.observations and any(o.success for o in runtime.observations):
            plan = mark_plan_terminal(plan, "partial")
        else:
            plan = mark_plan_terminal(plan, "blocked")
    elif runtime.observations and all(o.success for o in runtime.observations):
        plan = mark_plan_terminal(plan, "completed")
    elif runtime.observations:
        plan = mark_plan_terminal(plan, "partial")
    elif answer.strip():
        plan = mark_plan_terminal(plan, "completed")
    else:
        plan = mark_plan_terminal(plan, "failed")
    plan.execution_strategy = "REACT"
    return plan, runtime.observations


def execution_plan_patch_from_react_runtime(
    runtime: ReactPlanRuntime,
    *,
    react_status: str,
    answer: str = "",
) -> dict[str, Any]:
    plan, observations = finalize_react_execution_plan(
        runtime,
        react_status=react_status,
        answer=answer,
    )
    from app.services.execution_plan_service import execution_plan_patch, observations_patch

    patch: dict[str, Any] = {**execution_plan_patch(plan), **observations_patch(observations)}
    patch["react_execution_plan_id"] = plan.plan_id
    return patch
