"""P1 — one-shot LIVE → classical governed execute without a second tool-choice."""
from __future__ import annotations

import json
from contextvars import ContextVar
from types import SimpleNamespace
from typing import Any

HANDOFF_REASONS = frozenset(
    {
        "read_tool_classical",
        "defer_classical_tool_sse",
        "defer_connector_tool_proposal",
        "evidence_plan_required_read",
    }
)

_armed: ContextVar[dict[str, Any] | None] = ContextVar("live_classical_handoff", default=None)
_armed_queue: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "live_classical_handoff_queue", default=None
)


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
    if isinstance(task_state, dict) and task_state.get("live_classical_handoff_queue"):
        # Evidence-plan required reads own the execute queue; LIVE must not replace them.
        existing = task_state.get("live_classical_handoff")
        return dict(existing) if isinstance(existing, dict) else None
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


def stash_handoff_queue(task_state: dict[str, Any] | None, queue: list[dict[str, Any]]) -> None:
    if not isinstance(task_state, dict) or not queue:
        return
    cleaned = [dict(item) for item in queue if isinstance(item, dict) and item.get("tool_name")]
    if not cleaned:
        return
    task_state["live_classical_handoff_queue"] = cleaned
    task_state["live_classical_handoff"] = dict(cleaned[0])
    task_state["evidence_plan_owns_tools"] = True


def arm_handoff(payload: dict[str, Any] | None) -> None:
    if isinstance(payload, dict) and payload.get("tool_name"):
        _armed.set(payload)
    else:
        _armed.set(None)


def arm_from_task_state(task_state: dict[str, Any] | None) -> None:
    payload = None
    queue: list[dict[str, Any]] | None = None
    if isinstance(task_state, dict):
        raw_q = task_state.get("live_classical_handoff_queue")
        if isinstance(raw_q, list) and raw_q:
            queue = [dict(x) for x in raw_q if isinstance(x, dict)]
        raw = task_state.get("live_classical_handoff")
        if isinstance(raw, dict):
            payload = raw
        elif queue:
            payload = queue[0]
    _armed_queue.set(queue)
    arm_handoff(payload)


def peek_handoff() -> dict[str, Any] | None:
    return _armed.get()


def consume_handoff() -> dict[str, Any] | None:
    queue = _armed_queue.get()
    if isinstance(queue, list) and queue:
        payload = dict(queue[0])
        rest = queue[1:]
        _armed_queue.set(rest if rest else None)
        _armed.set(dict(rest[0]) if rest else None)
        return payload
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
