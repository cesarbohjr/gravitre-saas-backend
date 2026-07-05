"""Structured execution status envelopes for chat and connector actions."""
from __future__ import annotations

from typing import Any, Literal

NotExecutableReason = Literal[
    "missing_scope",
    "missing_connector",
    "missing_permission",
    "not_implemented",
    "requires_approval",
    "token_expired",
    "unsupported_action",
]


def build_not_executable(
    reason: NotExecutableReason | str,
    *,
    next_step: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "not_executable",
        "reason": reason,
        "next_step": next_step,
        "metadata": metadata or {},
    }


def format_not_executable_message(payload: dict[str, Any]) -> str:
    reason = str(payload.get("reason") or "not_implemented")
    next_step = str(payload.get("next_step") or "").strip()
    labels = {
        "missing_scope": "This action needs a connector scope that is not configured.",
        "missing_connector": "No connected integration supports this action yet.",
        "missing_permission": "Your role does not allow this action.",
        "not_implemented": "This action is not available yet.",
        "requires_approval": "This action requires explicit approval before it can run.",
        "token_expired": "The connector is configured, but authentication has expired.",
        "unsupported_action": "This connector action is not supported yet.",
    }
    base = labels.get(reason, "This action cannot run right now.")
    return f"{base} {next_step}".strip()
