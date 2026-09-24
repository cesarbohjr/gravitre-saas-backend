"""3.0-I governed spoken WRITE — confirm vs yes-wait, bound to PendingAction.

Never invoke a WRITE on hold, stale, foreign, or ambiguous speech.
Typed and spoken share this classifier. Not a second voice runtime.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

SpokenWriteDecision = Literal[
    "confirm",
    "hold_commit",
    "reject",
    "clarify",
    "stale",
    "none",
]

AUDIT_SPOKEN_WRITE = "spoken_write.classified"
PENDING_WRITE_TTL_SECONDS = 30 * 60
_TERMINAL = frozenset(
    {
        "cancelled",
        "declined",
        "rejected",
        "completed",
        "executed",
        "verified",
        "expired",
        "failed",
    }
)
_IN_FLIGHT = frozenset({"executing", "claimed"})
_AWAITING = frozenset(
    {
        "awaiting_confirm",
        "awaiting_admin_approval",
        "awaiting_user",
        "awaiting_user_confirmation",
        "awaiting_approval",
    }
)

# "yes wait" / "yeah, hold on" is not approval. Bare "wait" stays DECLINE.
_YES_WAIT_RE = re.compile(
    r"^\s*(?:yes|yeah|yep|y|ok|okay|sure)[,.\s]+"
    r"(?:wait|hold(?:\s+on)?|not\s+yet|pause|hang\s+on)"
    r"(?:\s+(?:a\s+)?(?:second|minute|moment|please))?\s*[.!]?\s*$",
    re.I,
)
_NATURAL_CONFIRM_RE = re.compile(
    r"^\s*(?:yes|yeah|yep|y|ok|okay|sure)[,.\s]+"
    r"(?:please\s+)?(?:create|do|send|approve|run|execute)(?:\s+it)?(?:\s+now)?"
    r"(?:\s+the\s+\w+)?"
    r"\s*[.!]?\s*$",
    re.I,
)
_AMBIGUOUS_RE = re.compile(
    r"(?is)\b("
    r"maybe|i think|not sure|inaudible|kind of|sort of|"
    r"if you want|whatever|i guess|probably"
    r")\b|^\s*(?:uh|um|huh|err)\s*[.?!]?\s*$"
)
_BARE_CONFIRM = frozenset(
    {
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
    }
)
_VENDORS = (
    "hubspot",
    "gmail",
    "apollo",
    "slack",
    "zendesk",
    "quickbooks",
    "google ads",
    "google_ads",
)


@dataclass(frozen=True)
class SpokenWriteApproval:
    decision: SpokenWriteDecision
    invoke_allowed: bool
    pending_action_id: str | None
    pending_target: str | None
    reason: str
    matched: bool
    invoke_action: str | None = None
    org_id: str | None = None
    actor_id: str | None = None
    conversation_id: str | None = None

    def as_trace(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "invoke_allowed": self.invoke_allowed,
            "pending_action_id": self.pending_action_id,
            "pending_target": self.pending_target,
            "reason": self.reason,
            "matched": self.matched,
            "invoke_action": self.invoke_action,
            "org_id": self.org_id,
            "actor_id": self.actor_id,
            "conversation_id": self.conversation_id,
            "provider_invoked": False if not self.invoke_allowed else None,
        }


def pending_write_row(task_state: dict[str, Any] | None) -> dict[str, Any]:
    state = task_state if isinstance(task_state, dict) else {}
    for key in ("pending_action", "pending_task", "offered_action"):
        row = state.get(key)
        if isinstance(row, dict) and row:
            return row
    return {}


def pending_write_action_id(task_state: dict[str, Any] | None) -> str | None:
    state = task_state if isinstance(task_state, dict) else {}
    row = pending_write_row(state)
    for field in ("id", "pending_action_id", "action_id"):
        value = row.get(field)
        if value:
            return str(value)
    plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    if plan.get("pending_action_id"):
        return str(plan.get("pending_action_id"))
    return None


def stamp_pending_write_binding(
    pending: dict[str, Any] | None,
    *,
    org_id: str,
    actor_id: str | None,
    conversation_id: str | None,
    invoke_action: str | None = None,
) -> dict[str, Any]:
    """Attach org/actor/conversation/expiry onto an existing pending_task. No new store."""
    out = dict(pending) if isinstance(pending, dict) else {}
    if not out.get("id") and not out.get("pending_action_id"):
        out["id"] = str(uuid4())
    out["org_id"] = str(org_id or out.get("org_id") or "")
    if actor_id:
        out["actor_id"] = str(actor_id)
    if conversation_id:
        out["conversation_id"] = str(conversation_id)
    action = str(invoke_action or out.get("invoke_action") or "").strip()
    params = dict(out.get("params") or {}) if isinstance(out.get("params"), dict) else {}
    if not action:
        action = str(params.get("invoke_action") or "").strip()
    if action:
        out["invoke_action"] = action
        params.setdefault("invoke_action", action)
        out["params"] = params
    if not out.get("expires_at"):
        out["expires_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=PENDING_WRITE_TTL_SECONDS)
        ).isoformat()
    return out


def format_spoken_hold_commit(*, pending_action_id: str | None = None) -> str:
    bound = f" (`{pending_action_id}`)" if pending_action_id else ""
    return (
        f"Write is on hold{bound}. I will not send or execute until you confirm with **yes**."
    )


def format_spoken_clarify() -> str:
    return (
        "I am not sure that was a clear approval. Say yes to run the staged action, "
        "or tell me what to change. I will not execute until then."
    )


def format_spoken_stale(*, reason: str) -> str:
    if reason in {"already_done", "pending_completed"}:
        return "That action already finished. I will not run it again."
    if reason in {"already_claimed", "pending_in_flight"}:
        return "That action is already running. I will not start a second write."
    if reason in {"pending_expired", "expired"}:
        return "That approval expired. I can stage the action again if you still want it."
    return "That pending action is no longer waiting for approval. I will not execute it."


def format_spoken_unauthorized() -> str:
    return "You can't approve this action for another person or organization."


def _parse_expiry(raw: str | None) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _pending_invoke_action(row: dict[str, Any]) -> str | None:
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    for key in ("invoke_action", "action", "action_key"):
        value = row.get(key) or params.get(key)
        if value:
            return str(value)
    return None


def _pending_integration(row: dict[str, Any]) -> str:
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    return str(row.get("integration") or params.get("integration") or "").strip().lower()


def _mentions_unrelated_vendor(text: str, pending_integration: str) -> bool:
    lowered = (text or "").lower()
    mentioned = [vendor for vendor in _VENDORS if vendor in lowered]
    if not mentioned or not pending_integration:
        return False
    pending = pending_integration.replace("_", " ")
    return all(pending not in vendor and vendor not in pending for vendor in mentioned)


def classify_spoken_write_approval(
    message: str,
    *,
    task_state: dict[str, Any] | None = None,
    expected_pending_id: str | None = None,
    expected_org_id: str | None = None,
    expected_actor_id: str | None = None,
    expected_conversation_id: str | None = None,
) -> SpokenWriteApproval:
    """Bind confirm/hold to the staged PendingAction. Hold never allows invoke."""
    from app.services.conversational_execution_service import CONFIRM_PATTERN, DECLINE_PATTERN
    from app.services.reference_resolver import _pending_confirmation_target

    text = (message or "").strip()
    state = task_state if isinstance(task_state, dict) else {}
    row = pending_write_row(state)
    pending_id = pending_write_action_id(state)
    pending_target = _pending_confirmation_target(state)
    invoke_action = _pending_invoke_action(row)
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    pending_org = str(row.get("org_id") or params.get("org_id") or "").strip() or None
    pending_actor = str(row.get("actor_id") or params.get("actor_id") or "").strip() or None
    pending_conv = str(row.get("conversation_id") or params.get("conversation_id") or "").strip() or None
    expected = str(expected_pending_id or pending_id or "").strip() or None
    status = str(row.get("status") or "").strip().lower()

    def _result(
        decision: SpokenWriteDecision,
        *,
        invoke_allowed: bool,
        reason: str,
        matched: bool,
    ) -> SpokenWriteApproval:
        return SpokenWriteApproval(
            decision=decision,
            invoke_allowed=invoke_allowed,
            pending_action_id=expected,
            pending_target=pending_target,
            reason=reason,
            matched=matched,
            invoke_action=invoke_action,
            org_id=pending_org,
            actor_id=pending_actor,
            conversation_id=pending_conv,
        )

    if not text:
        return _result("none", invoke_allowed=False, reason="empty_message", matched=False)

    if _YES_WAIT_RE.match(text):
        return _result("hold_commit", invoke_allowed=False, reason="yes_wait_hold_commit", matched=True)

    if DECLINE_PATTERN.match(text):
        return _result("reject", invoke_allowed=False, reason="spoken_reject", matched=bool(pending_target))

    if _AMBIGUOUS_RE.search(text) and re.match(r"(?i)^\s*(?:yes|yeah|yep|ok|okay|sure)\b", text):
        return _result("clarify", invoke_allowed=False, reason="ambiguous_spoken_confirm", matched=True)

    looks_confirm = bool(
        CONFIRM_PATTERN.match(text)
        or _NATURAL_CONFIRM_RE.match(text)
        or text.lower() in _BARE_CONFIRM
    )
    if not looks_confirm:
        return _result("none", invoke_allowed=False, reason="no_spoken_write_match", matched=False)

    if _AMBIGUOUS_RE.search(text):
        return _result("clarify", invoke_allowed=False, reason="ambiguous_spoken_confirm", matched=True)

    if expected_pending_id and pending_id and str(pending_id) != str(expected_pending_id):
        return _result("none", invoke_allowed=False, reason="pending_action_mismatch", matched=False)

    if expected_org_id and pending_org and str(pending_org) != str(expected_org_id):
        return _result("stale", invoke_allowed=False, reason="foreign_org", matched=True)
    if expected_actor_id and pending_actor and str(pending_actor) != str(expected_actor_id):
        return _result("stale", invoke_allowed=False, reason="foreign_actor", matched=True)
    if expected_conversation_id and pending_conv and str(pending_conv) != str(expected_conversation_id):
        return _result("stale", invoke_allowed=False, reason="foreign_conversation", matched=True)

    expiry = _parse_expiry(str(row.get("expires_at") or "") or None)
    if expiry is not None and expiry <= datetime.now(timezone.utc):
        return _result("stale", invoke_allowed=False, reason="pending_expired", matched=True)

    if status in _TERMINAL:
        reason = "already_done" if status in {"completed", "executed", "verified"} else f"pending_{status}"
        return _result("stale", invoke_allowed=False, reason=reason, matched=True)
    if status in _IN_FLIGHT:
        return _result("stale", invoke_allowed=False, reason="already_claimed", matched=True)
    if status and status not in _AWAITING:
        return _result("stale", invoke_allowed=False, reason=f"pending_{status}", matched=True)

    if _mentions_unrelated_vendor(text, _pending_integration(row)):
        return _result("clarify", invoke_allowed=False, reason="unrelated_vendor_confirm", matched=True)

    if not pending_target:
        return _result("confirm", invoke_allowed=False, reason="no_pending_confirmation", matched=False)

    return _result("confirm", invoke_allowed=True, reason=f"confirm_{pending_target}", matched=True)
