"""Canonical LIVE fallthrough_reason enum (routing map B.1 / F10).

Every `_mark_live_fallthrough` reason must be in LIVE_FALLTHROUGH_REASONS or
match a documented dynamic prefix (outcome_*, unhandled_kind_*).
"""
from __future__ import annotations

from typing import Final

# Exact reasons emitted by apply_unified_turn_live / helpers.
LIVE_FALLTHROUGH_REASONS: Final[frozenset[str]] = frozenset(
    {
        "live_disabled",
        "pending_family_classical_resume",
        "outcome_skipped",
        "outcome_error",
        "defer_classical_tool_sse",
        "defer_connector_tool_proposal",
        "violates_no_pending_hold",
        "false_connector_disconnect_claim",
        "write_plan_unavailable",
        "read_tool_classical",
    }
)

# Dynamic families — suffix is free-form outcome_kind.
LIVE_FALLTHROUGH_PREFIXES: Final[tuple[str, ...]] = (
    "outcome_",
    "unhandled_kind_",
)


def is_known_fallthrough_reason(reason: str | None) -> bool:
    text = str(reason or "").strip()
    if not text:
        return False
    if text in LIVE_FALLTHROUGH_REASONS:
        return True
    return any(text.startswith(prefix) for prefix in LIVE_FALLTHROUGH_PREFIXES)


def assert_known_fallthrough_reason(reason: str | None) -> str:
    text = str(reason or "").strip()
    if not is_known_fallthrough_reason(text):
        raise ValueError(f"unknown fallthrough_reason: {text!r}")
    return text
