"""Phase E5 — ExecutionPlan authority helpers (canonical SoT enforcement)."""
from __future__ import annotations

from typing import Any

from app.services.execution_plan_service import ExecutionPlan


def authoritative_execution_plan(state: dict[str, Any] | None) -> ExecutionPlan | None:
    """Return the canonical ExecutionPlan when present and non-terminal."""
    plan = ExecutionPlan.from_dict((state or {}).get("execution_plan"))
    if plan is None:
        return None
    return plan


def plan_id_from_state(state: dict[str, Any] | None) -> str | None:
    plan = authoritative_execution_plan(state)
    if plan is not None:
        return plan.plan_id
    pending_action = (state or {}).get("pending_action")
    if isinstance(pending_action, dict) and pending_action.get("plan_id"):
        return str(pending_action["plan_id"])
    offered = (state or {}).get("offered_action")
    if isinstance(offered, dict) and offered.get("execution_plan_id"):
        return str(offered["execution_plan_id"])
    pending = (state or {}).get("pending_task")
    if isinstance(pending, dict) and pending.get("execution_plan_id"):
        return str(pending["execution_plan_id"])
    return None


def is_legacy_ingress_only(pending: dict[str, Any] | None, *, canonical: ExecutionPlan | None) -> bool:
    """True when pending_task may be adapted into ExecutionPlan (no canonical plan yet)."""
    if canonical is not None:
        return False
    if not isinstance(pending, dict):
        return False
    if pending.get("execution_plan_id"):
        return False
    return pending.get("status") not in {None, "completed", "failed", "cancelled"}


def pending_task_is_projection(pending: dict[str, Any] | None) -> bool:
    return isinstance(pending, dict) and bool(pending.get("_projection"))


def strategic_plan_only(current_plan: dict[str, Any] | None) -> bool:
    """Non-executable strategic plans must not drive tool execution."""
    if not isinstance(current_plan, dict):
        return False
    if current_plan.get("executable") is True:
        return False
    kind = str(current_plan.get("plan_kind") or current_plan.get("kind") or "").lower()
    return kind in {"strategic", "strategic_reasoning", ""} or current_plan.get("executable") is False
