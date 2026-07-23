"""Shared helpers for live unified-turn audit queries (LIVE vs shadow)."""
from __future__ import annotations

from typing import Any


def unified_turn_completed_action(health: dict[str, Any] | None) -> str:
    """Audit action written when a unified turn finishes on the user path."""
    if health and bool(health.get("unified_turn_live_enabled")):
        return "unified_turn.live.completed"
    return "unified_turn.shadow.completed"


def unified_turn_completed_actions(health: dict[str, Any] | None) -> list[str]:
    """Actions to query when either path may have run (newest wins)."""
    live = unified_turn_completed_action(health)
    if live == "unified_turn.live.completed":
        return ["unified_turn.live.completed", "unified_turn.shadow.completed"]
    return ["unified_turn.shadow.completed", "unified_turn.live.completed"]
