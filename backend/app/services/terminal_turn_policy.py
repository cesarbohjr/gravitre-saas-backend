"""Phase C — enforce terminal turn outcomes (no silent deferred I'll-check)."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.offered_action_continuation import claims_future_action

logger = get_logger(__name__)

TERMINAL_WORKFLOW_STATUSES = frozenset(
    {
        "completed",
        "failed",
        "blocked",
        "needs clarification",
        "partial",
        "connector_not_connected",
        "catalog_gap",
    }
)

_HONEST_BLOCKED = (
    "I couldn't finish a live read on this turn. "
    "Check **Connectors** for authorization, then ask again with the same request."
)


def _has_deferred_work(task_state: dict[str, Any] | None) -> bool:
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task")
    if isinstance(pending, dict) and pending.get("status") in {
        "awaiting_confirm",
        "awaiting_plan_confirm",
        "awaiting_params",
        "awaiting_step_confirm",
        "awaiting_admin_approval",
    }:
        return True
    offered = state.get("offered_action")
    if isinstance(offered, dict) and offered.get("status") in {
        "awaiting_user_confirmation",
        "awaiting_confirm",
    }:
        return True
    plan = state.get("execution_plan")
    if isinstance(plan, dict) and str(plan.get("terminal_status") or "") == "pending":
        steps = plan.get("steps")
        if isinstance(steps, list) and any(
            isinstance(s, dict) and s.get("status") == "pending" for s in steps
        ):
            return True
    return False


def enforce_terminal_turn_outcome(
    message: str,
    *,
    task_state: dict[str, Any] | None = None,
    workflow_status: str | None = None,
) -> str:
    """Replace non-terminal defer language when no durable pending work exists."""
    text = (message or "").strip()
    if not text:
        return text
    if _has_deferred_work(task_state):
        return text
    status = str(workflow_status or "").strip().lower()
    if status in TERMINAL_WORKFLOW_STATUSES:
        return text
    if not claims_future_action(text):
        return text
    logger.info(
        "terminal_turn_policy_blocked_defer workflow_status=%s message_prefix=%s",
        status,
        text[:80],
    )
    return _HONEST_BLOCKED
