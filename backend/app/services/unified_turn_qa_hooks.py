"""QA-only hooks for deterministic unified-turn gate verification.

Force a connector tool proposal without depending on model mis-selection.
Active only when ``unified_turn_qa_hooks_enabled`` is true AND a per-request
header or ``UNIFIED_TURN_QA_FORCE_TOOL`` env is set — no effect on normal chat.
"""
from __future__ import annotations

import os
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

QA_FORCE_TOOL_HEADER = "X-Gravitre-QA-Force-Tool"
QA_FORCE_OUTCOME_HEADER = "X-Gravitre-QA-Force-Outcome"


def resolve_qa_force_tool(
    settings: Any,
    *,
    header_value: str | None = None,
) -> str | None:
    if not getattr(settings, "unified_turn_qa_hooks_enabled", False):
        return None
    raw = (header_value or "").strip() or (os.environ.get("UNIFIED_TURN_QA_FORCE_TOOL") or "").strip()
    if not raw:
        return None
    return raw


def resolve_qa_force_outcome(
    settings: Any,
    *,
    header_value: str | None = None,
) -> str | None:
    if not getattr(settings, "unified_turn_qa_hooks_enabled", False):
        return None
    raw = (header_value or "").strip() or (
        os.environ.get("UNIFIED_TURN_QA_FORCE_OUTCOME") or ""
    ).strip()
    if not raw:
        return None
    allowed = {
        "knowledge_boundary",
        "clarifying_question",
        "phantom_pending_hold",
    }
    token = raw.lower()
    if token not in allowed:
        raise ValueError(f"unknown QA force outcome: {raw}")
    return token


def synthetic_qa_outcome(outcome: str, *, message: str) -> dict[str, str]:
    """Deterministic user-visible copy for forced rare gates."""
    if outcome == "knowledge_boundary":
        return {
            "outcome_kind": "knowledge_boundary",
            "user_message": (
                "I don't have run history or execution counts from a real tool call this turn. "
                "Connect the relevant integration or ask me to check connector status first."
            ),
        }
    if outcome == "clarifying_question":
        return {
            "outcome_kind": "clarifying_question",
            "user_message": (
                "You have a pending item that isn't finished. Your new message looks like a "
                "different request. Say **hold** to keep working on the pending item, or "
                "**abandon** to discard it and switch."
            ),
        }
    if outcome == "phantom_pending_hold":
        # Invented hold/abandon without pending state — triggers violates_no_pending_hold guard.
        return {
            "outcome_kind": "conversational_reply",
            "user_message": (
                "You have something pending. Reply **hold** to keep working on it, "
                "or **abandon** to discard it and switch."
            ),
        }
    raise ValueError(outcome)


def registry_tool_for_force(registry: Any, force: str) -> tuple[str, str, dict[str, Any]]:
    """Map invoke action (gmail.messages.batch) or registry name (gmail_messages_batch)."""
    token = str(force or "").strip()
    if not token:
        raise ValueError("empty QA force tool")
    specs = getattr(registry, "_specs", {}) or {}
    for spec in specs.values():
        invoke = str(getattr(spec, "invoke_action", "") or "")
        name = str(getattr(spec, "name", "") or "")
        if token == invoke or token == name:
            return name, invoke, {}
    alt = token.replace(".", "_")
    spec = specs.get(alt)
    if spec is not None:
        return (
            str(getattr(spec, "name", "") or alt),
            str(getattr(spec, "invoke_action", "") or ""),
            {},
        )
    raise ValueError(f"unknown QA force tool: {token}")
