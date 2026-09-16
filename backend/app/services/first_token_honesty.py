"""First-token honesty (Phase F2).

Status and tool-intent must reach the UI before any completion claim.
Standalone "Done." is allowed only when the envelope + write gate agree.
"""
from __future__ import annotations

import re
from typing import Any

STAGE_PLAN = "plan"
STAGE_TOOL = "tool"
STAGE_COMPOSE = "compose"

STAGE_STATUS: dict[str, str] = {
    STAGE_PLAN: "Understanding your request",
    STAGE_TOOL: "Running connected tools",
    STAGE_COMPOSE: "Composing a response",
}

_STANDALONE_DONE = re.compile(r"^\s*done\.?\s*$", re.I)

_PENDING_STATUSES = frozenset(
    {"awaiting_confirm", "pending", "needs_approval", "awaiting_approval"}
)


def status_for_stage(stage: str) -> str:
    return STAGE_STATUS.get((stage or "").strip().lower(), STAGE_STATUS[STAGE_PLAN])


def envelope_allows_completion_claim(envelope: dict[str, Any] | None) -> bool:
    """True only when a verified successful write (or explicit verified flag) exists."""
    env = envelope if isinstance(envelope, dict) else {}
    if env.get("success") is False:
        return False
    pending = env.get("pending_task")
    data = env.get("data") if isinstance(env.get("data"), dict) else {}
    if not isinstance(pending, dict):
        pending = data.get("pending_task") if isinstance(data.get("pending_task"), dict) else None
    if isinstance(pending, dict):
        status = str(pending.get("status") or "").strip().lower()
        if status in _PENDING_STATUSES:
            return False
    if env.get("write_approval_required") or env.get("needs_approval"):
        return False
    if data.get("write_approval_required") or data.get("needs_approval"):
        return False
    if env.get("execution_verified") is False or data.get("execution_verified") is False:
        return False
    return bool(env.get("execution_verified") is True or data.get("execution_verified") is True)


def is_standalone_done(text: str | None) -> bool:
    return bool(_STANDALONE_DONE.match(text or ""))


def reject_premature_done(text: str, envelope: dict[str, Any] | None, *, fallback: str) -> str:
    """Keep model prose; replace a bare Done. when the write was not verified."""
    cleaned = (text or "").strip()
    if not cleaned:
        return fallback
    if is_standalone_done(cleaned) and not envelope_allows_completion_claim(envelope):
        return fallback
    return cleaned
