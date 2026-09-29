"""Phase E5 — ExecutionPlan authority helpers (canonical SoT enforcement)."""
from __future__ import annotations

from typing import Any

from app.services.execution_plan_service import ExecutionPlan

_PROTECTED_WRITE_TERMINALS = frozenset({"completed", "partial", "failed", "blocked", "cancelled"})
_WEAK_PLAN_SOURCES = frozenset({"default_compose", "compose", "react", "current_plan"})


def is_terminal_write_plan(plan: ExecutionPlan | None) -> bool:
    """True when the plan already records a finished WRITE, not in-flight work."""
    if plan is None:
        return False
    if plan.terminal_status not in _PROTECTED_WRITE_TERMINALS:
        return False
    writes = [step for step in plan.steps if step.kind == "write"]
    if plan.source in {"connector_write", "connector_action"}:
        return True
    if not writes:
        return False
    return all(step.status not in {"pending", "running"} for step in writes)


def prefer_persisted_write_plan(
    current: ExecutionPlan | None,
    incoming: ExecutionPlan | None,
) -> ExecutionPlan | None:
    """Keep verified WRITE terminal truth; do not let follow-up compose reset pending."""
    if incoming is None:
        return current
    if current is None or not is_terminal_write_plan(current):
        return incoming
    if incoming.terminal_status == "waiting_for_approval":
        return incoming
    if incoming.terminal_status in _PROTECTED_WRITE_TERMINALS:
        return incoming
    same_id = incoming.plan_id == current.plan_id
    weak = incoming.source in _WEAK_PLAN_SOURCES or incoming.replan_reason == "follow_up"
    if not (same_id or weak):
        return incoming
    current.turn_id = incoming.turn_id or current.turn_id
    current.conversation_id = incoming.conversation_id or current.conversation_id
    current.revision = max(int(current.revision or 1), int(incoming.revision or 1))
    if incoming.replan_reason:
        current.replan_reason = incoming.replan_reason
    return current


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
