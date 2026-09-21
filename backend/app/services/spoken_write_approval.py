"""3.0-I governed spoken WRITE — confirm vs yes-wait, bound to PendingAction.

Never invoke a WRITE on hold. Typed and spoken share this classifier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

SpokenWriteDecision = Literal["confirm", "hold_commit", "reject", "none"]

AUDIT_SPOKEN_WRITE = "spoken_write.classified"

# "yes wait" / "yeah, hold on" is not approval. Bare "wait" stays DECLINE.
_YES_WAIT_RE = re.compile(
    r"^\s*(?:yes|yeah|yep|y|ok|okay|sure)[,.\s]+"
    r"(?:wait|hold(?:\s+on)?|not\s+yet|pause|hang\s+on)"
    r"(?:\s+(?:a\s+)?(?:second|minute|moment|please))?\s*[.!]?\s*$",
    re.I,
)


@dataclass(frozen=True)
class SpokenWriteApproval:
    decision: SpokenWriteDecision
    invoke_allowed: bool
    pending_action_id: str | None
    pending_target: str | None
    reason: str
    matched: bool

    def as_trace(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "invoke_allowed": self.invoke_allowed,
            "pending_action_id": self.pending_action_id,
            "pending_target": self.pending_target,
            "reason": self.reason,
            "matched": self.matched,
            "provider_invoked": False if not self.invoke_allowed else None,
        }


def pending_write_action_id(task_state: dict[str, Any] | None) -> str | None:
    state = task_state if isinstance(task_state, dict) else {}
    for key in ("pending_action", "pending_task", "offered_action"):
        row = state.get(key)
        if not isinstance(row, dict):
            continue
        for field in ("id", "pending_action_id", "action_id"):
            value = row.get(field)
            if value:
                return str(value)
    plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    if plan.get("pending_action_id"):
        return str(plan.get("pending_action_id"))
    return None


def format_spoken_hold_commit(*, pending_action_id: str | None = None) -> str:
    bound = f" (`{pending_action_id}`)" if pending_action_id else ""
    return (
        f"Write is on hold{bound}. I will not send or execute until you confirm with **yes**."
    )


def classify_spoken_write_approval(
    message: str,
    *,
    task_state: dict[str, Any] | None = None,
    expected_pending_id: str | None = None,
) -> SpokenWriteApproval:
    """Bind confirm/hold to the staged PendingAction. Hold never allows invoke."""
    from app.services.conversational_execution_service import CONFIRM_PATTERN, DECLINE_PATTERN
    from app.services.reference_resolver import _pending_confirmation_target

    text = (message or "").strip()
    state = task_state if isinstance(task_state, dict) else {}
    pending_id = pending_write_action_id(state)
    pending_target = _pending_confirmation_target(state)
    expected = str(expected_pending_id or pending_id or "").strip() or None

    if not text:
        return SpokenWriteApproval(
            decision="none",
            invoke_allowed=False,
            pending_action_id=expected,
            pending_target=pending_target,
            reason="empty_message",
            matched=False,
        )

    if _YES_WAIT_RE.match(text):
        return SpokenWriteApproval(
            decision="hold_commit",
            invoke_allowed=False,
            pending_action_id=expected,
            pending_target=pending_target,
            reason="yes_wait_hold_commit",
            matched=True,
        )

    if DECLINE_PATTERN.match(text):
        return SpokenWriteApproval(
            decision="reject",
            invoke_allowed=False,
            pending_action_id=expected,
            pending_target=pending_target,
            reason="spoken_reject",
            matched=bool(pending_target),
        )

    if CONFIRM_PATTERN.match(text) or text.lower() in {
        "yes",
        "y",
        "yeah",
        "yep",
        "ok",
        "okay",
        "confirm",
        "run",
        "execute",
        "approve",
    }:
        if expected_pending_id and pending_id and str(pending_id) != str(expected_pending_id):
            return SpokenWriteApproval(
                decision="none",
                invoke_allowed=False,
                pending_action_id=pending_id,
                pending_target=pending_target,
                reason="pending_action_mismatch",
                matched=False,
            )
        if not pending_target:
            return SpokenWriteApproval(
                decision="confirm",
                invoke_allowed=False,
                pending_action_id=expected,
                pending_target=None,
                reason="no_pending_confirmation",
                matched=False,
            )
        return SpokenWriteApproval(
            decision="confirm",
            invoke_allowed=True,
            pending_action_id=expected,
            pending_target=pending_target,
            reason=f"confirm_{pending_target}",
            matched=True,
        )

    return SpokenWriteApproval(
        decision="none",
        invoke_allowed=False,
        pending_action_id=expected,
        pending_target=pending_target,
        reason="no_spoken_write_match",
        matched=False,
    )
