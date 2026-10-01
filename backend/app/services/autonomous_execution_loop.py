"""Phase 3 bounded autonomous execution-loop policy over E5 ExecutionPlan.

This module does not execute tools. It decides what the existing runtime may do
after each observation: continue, verify, replan, wait, complete, or stop.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.durable_work_session import stop_reason, verify_before_complete
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep, replan_execution_plan

LoopAction = Literal["continue", "verify", "replan", "wait_approval", "wait_user", "complete", "stop"]


@dataclass(frozen=True)
class ExecutionLoopDecision:
    action: LoopAction
    reason: str
    plan: ExecutionPlan
    next_step_id: str | None = None
    terminal: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "plan_id": self.plan.plan_id,
            "revision": self.plan.revision,
            "replans_used": self.plan.replans_used,
            "next_step_id": self.next_step_id,
            "terminal": self.terminal,
        }


def _pending_step(plan: ExecutionPlan) -> ExecutionStep | None:
    return next((step for step in plan.steps if step.status == "pending"), None)


def _provider_write_verified(task_state: dict[str, Any], observations: list[dict[str, Any]]) -> bool:
    """Accepted or queued is not provider proof."""
    evidence = task_state.get("provider_result_evidence")
    if isinstance(evidence, dict):
        status = str(evidence.get("verification_status") or evidence.get("status") or "").lower()
        if status in {"verified", "completed", "confirmed"} and (
            evidence.get("provider_record_id") or evidence.get("provider_id") or evidence.get("verified") is True
        ):
            return True
    for row in reversed(observations):
        if not isinstance(row, dict) or not row.get("success"):
            continue
        structured = row.get("structured") if isinstance(row.get("structured"), dict) else {}
        status = str(structured.get("verification_status") or structured.get("provider_status") or "").lower()
        if status in {"verified", "completed", "confirmed"} and (
            structured.get("provider_record_id") or structured.get("provider_id") or structured.get("vendor_proof")
        ):
            return True
    return False


def _waiting_state(task_state: dict[str, Any]) -> tuple[LoopAction | None, str | None]:
    pending = task_state.get("pending_action")
    if not isinstance(pending, dict):
        pending = task_state.get("pending_task")
    if not isinstance(pending, dict):
        return None, None
    status = str(pending.get("status") or "").strip().lower()
    if status in {"awaiting_confirm", "awaiting_user_confirmation", "awaiting_approval"}:
        return "wait_approval", "approval_required"
    if status in {"awaiting_user", "needs_input", "clarification_required"}:
        return "wait_user", "user_input_required"
    return None, None


def decide_execution_loop(
    *,
    plan: ExecutionPlan,
    task_state: dict[str, Any] | None,
    observations: list[dict[str, Any]] | None = None,
    iterations_used: int = 0,
    iteration_budget: int = 8,
    tools_used: int = 0,
    tool_budget: int = 12,
    elapsed_ms: int | None = None,
    time_budget_ms: int = 120_000,
    alternate_read_steps: list[ExecutionStep] | None = None,
) -> ExecutionLoopDecision:
    """Choose the next legal transition after OBSERVE.

    alternate_read_steps must come from an existing repair/replanner. This policy
    never invents connector actions.
    """
    state = task_state if isinstance(task_state, dict) else {}
    obs = [row for row in (observations or state.get("execution_observations") or []) if isinstance(row, dict)]

    wait_action, wait_reason = _waiting_state(state)
    if wait_action is not None:
        plan.terminal_status = "waiting_for_approval" if wait_action == "wait_approval" else "clarification_required"
        return ExecutionLoopDecision(wait_action, wait_reason or "waiting", plan)

    budget_stop = stop_reason(
        iterations_used=iterations_used,
        iteration_budget=iteration_budget,
        tools_used=tools_used,
        tool_budget=tool_budget,
        elapsed_ms=elapsed_ms,
        time_budget_ms=time_budget_ms,
    )
    if budget_stop:
        plan.terminal_status = "partial" if obs else "failed"
        return ExecutionLoopDecision("stop", budget_stop, plan, terminal=True)

    failed = [step for step in plan.steps if step.status == "failed"]
    if failed:
        if any(step.kind == "write" for step in failed):
            plan.terminal_status = "partial"
            return ExecutionLoopDecision("verify", "write_failed_or_uncertain", plan)
        alternatives = list(alternate_read_steps or [])
        if alternatives and plan.replans_used < plan.replan_budget:
            replanned = replan_execution_plan(
                plan,
                new_steps=alternatives,
                reason="observation_failure",
                evidence={"failed_step_ids": [step.step_id for step in failed]},
            )
            next_step = _pending_step(replanned)
            return ExecutionLoopDecision(
                "replan",
                "bounded_read_replan",
                replanned,
                next_step_id=next_step.step_id if next_step else None,
            )
        plan.terminal_status = "partial" if any(row.get("success") for row in obs) else "failed"
        return ExecutionLoopDecision("stop", "no_safe_replan_available", plan, terminal=True)

    pending = _pending_step(plan)
    if pending is not None:
        plan.terminal_status = "running"
        return ExecutionLoopDecision("continue", "next_plan_step", plan, next_step_id=pending.step_id)

    writes = [step for step in plan.steps if step.kind == "write"]
    write_verified = _provider_write_verified(state, obs) if writes else None
    ok, reason = verify_before_complete(
        plan=plan,
        observations=obs,
        write_verified=write_verified,
        blockers=[],
    )
    if not ok:
        plan.terminal_status = "running"
        return ExecutionLoopDecision("verify", reason, plan)

    plan.terminal_status = "completed"
    return ExecutionLoopDecision("complete", "verified_complete", plan, terminal=True)
