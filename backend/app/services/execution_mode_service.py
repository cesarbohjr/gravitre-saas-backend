"""Execution mode contract for Intelligence runs (STA-266 / 2A step 3)."""
from __future__ import annotations

from typing import Any, Literal

ExecutionMode = Literal["tools_executed", "advisory_only", "degraded"]


def resolve_execution_mode(
    *,
    react_status: str,
    tool_calls: list[dict[str, Any]] | None,
    error: str | None = None,
) -> ExecutionMode:
    status = (react_status or "").lower()
    if error or status in {"error", "max_iterations_reached"}:
        return "degraded"
    calls = tool_calls or []
    successes = sum(1 for call in calls if (call.get("result") or {}).get("success"))
    if successes > 0:
        return "tools_executed"
    return "advisory_only"


def resolve_execution_verified(
    *,
    tools_available: int,
    tool_calls: list[dict[str, Any]] | None,
) -> bool:
    if tools_available <= 0:
        return False
    calls = tool_calls or []
    if not calls:
        return False
    return any((call.get("result") or {}).get("success") for call in calls)
