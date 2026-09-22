"""P1 — one-shot LIVE → classical governed execute without a second tool-choice."""
from __future__ import annotations

import json
from contextvars import ContextVar
from types import SimpleNamespace
from typing import Any

HANDOFF_REASONS = frozenset({"read_tool_classical", "defer_classical_tool_sse", "defer_connector_tool_proposal"})

_armed: ContextVar[dict[str, Any] | None] = ContextVar("live_classical_handoff", default=None)


def p1_single_selection_enabled(settings: Any | None) -> bool:
    if settings is None:
        return True
    return bool(getattr(settings, "convergence_p1_single_selection_v1", True))


def stash_live_classical_handoff(
    task_state: dict[str, Any] | None,
    result: Any,
    *,
    reason: str,
    settings: Any | None = None,
) -> dict[str, Any] | None:
    if not p1_single_selection_enabled(settings):
        return None
    if reason not in HANDOFF_REASONS:
        return None
    tool_name = str(getattr(result, "tool_name", None) or "").strip()
    invoke = str(getattr(result, "tool_invoke_action", None) or "").strip()
    args = getattr(result, "tool_arguments", None)
    if not tool_name and not invoke:
        return None
    payload = {
        "tool_name": tool_name or invoke,
        "tool_invoke_action": invoke or tool_name,
        "tool_arguments": dict(args) if isinstance(args, dict) else {},
        "fallthrough_reason": reason,
        "single_selection": True,
    }
    if isinstance(task_state, dict):
        task_state["live_classical_handoff"] = payload
    return payload


def arm_handoff(payload: dict[str, Any] | None) -> None:
    if isinstance(payload, dict) and payload.get("tool_name"):
        _armed.set(payload)
    else:
        _armed.set(None)


def arm_from_task_state(task_state: dict[str, Any] | None) -> None:
    payload = None
    if isinstance(task_state, dict):
        raw = task_state.get("live_classical_handoff")
        if isinstance(raw, dict):
            payload = raw
    arm_handoff(payload)


def peek_handoff() -> dict[str, Any] | None:
    return _armed.get()


def consume_handoff() -> dict[str, Any] | None:
    payload = _armed.get()
    _armed.set(None)
    return dict(payload) if isinstance(payload, dict) else None


def fake_tool_choice_response(payload: dict[str, Any]) -> Any:
    """OpenAI-shaped response so ReAct executes LIVE's proposal without a model round."""
    name = str(payload.get("tool_name") or payload.get("tool_invoke_action") or "")
    args = payload.get("tool_arguments") if isinstance(payload.get("tool_arguments"), dict) else {}
    fn = SimpleNamespace(name=name, arguments=json.dumps(args))
    tc = SimpleNamespace(id="live_handoff_1", function=fn, type="function")
    message = SimpleNamespace(content="", tool_calls=[tc])
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], model="live_classical_handoff")
