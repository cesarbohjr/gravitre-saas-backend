"""Map assistant/ReAct streaming events to AI SDK UI SSE chunks."""
from __future__ import annotations

import json
import uuid
from typing import Any

from app.operators.assistant_mode_config import REGISTRY_TO_ASSISTANT_DISPLAY
from app.operators.stream_events import AssistantStreamEvent
from app.services.assistant_tools import TOOL_DISPLAY_NAMES


def _sse(chunk: dict[str, Any]) -> AssistantStreamEvent:
    data = dict(chunk)
    sse_type = str(data.pop("type"))
    return AssistantStreamEvent(sse_type=sse_type, payload=data)


def sse_start() -> AssistantStreamEvent:
    return _sse({"type": "start"})


def sse_start_step() -> AssistantStreamEvent:
    return _sse({"type": "start-step"})


def sse_finish_step() -> AssistantStreamEvent:
    return _sse({"type": "finish-step"})


def sse_finish() -> AssistantStreamEvent:
    return _sse({"type": "finish"})


def sse_done() -> str:
    return "data: [DONE]\n\n"


def sse_error(message: str) -> AssistantStreamEvent:
    return _sse({"type": "error", "errorText": message})


def sse_suggestions(suggestions: list[str]) -> AssistantStreamEvent:
    return _sse({"type": "data-suggestions", "data": {"suggestions": suggestions}})


def sse_knowledge_base_tool(
    *,
    call_id: str,
    query: str,
    output: dict[str, Any],
) -> list[AssistantStreamEvent]:
    display = TOOL_DISPLAY_NAMES["knowledge_base"]
    return [
        _sse(
            {
                "type": "tool-input-available",
                "toolCallId": call_id,
                "toolName": display,
                "input": {"query": query, "limit": 5},
            }
        ),
        _sse(
            {
                "type": "tool-output-available",
                "toolCallId": call_id,
                "output": output,
            }
        ),
    ]


def sse_react_tool_start(
    *,
    call_id: str,
    registry_tool_name: str,
    tool_args: dict[str, Any] | None,
) -> AssistantStreamEvent:
    display = REGISTRY_TO_ASSISTANT_DISPLAY.get(registry_tool_name) or registry_tool_name
    tool_input: dict[str, Any] = dict(tool_args or {})
    if "query" not in tool_input and registry_tool_name == "web_search":
        tool_input.setdefault("query", tool_args.get("query") if tool_args else "")
    return _sse(
        {
            "type": "tool-input-available",
            "toolCallId": call_id,
            "toolName": display,
            "input": tool_input or {"query": tool_args.get("query", "") if tool_args else ""},
        }
    )


def format_react_tool_output(registry_tool_name: str, observation: dict[str, Any]) -> dict[str, Any]:
    """Shape ToolRegistry observations like legacy assistant_tools outputs for UI chips."""
    if registry_tool_name == "web_search":
        results = observation.get("results") or []
        sources = observation.get("sources") or [
            {"title": row.get("title"), "url": row.get("url"), "excerpt": row.get("snippet")}
            for row in results
            if isinstance(row, dict)
        ]
        query = observation.get("query") or ""
        if observation.get("success") is False:
            return {
                "results": [],
                "totalResults": 0,
                "error": observation.get("error") or "web search unavailable",
                "query": query,
            }
        return {
            "results": results,
            "sources": sources,
            "totalResults": observation.get("totalResults", len(results)),
            "query": query,
        }
    if observation.get("success") is False:
        return {"error": observation.get("error") or "Tool failed"}
    payload = observation.get("result")
    if isinstance(payload, dict):
        return payload
    return observation


def sse_react_tool_complete(
    *,
    call_id: str,
    registry_tool_name: str,
    observation: dict[str, Any],
) -> AssistantStreamEvent:
    return _sse(
        {
            "type": "tool-output-available",
            "toolCallId": call_id,
            "output": format_react_tool_output(registry_tool_name, observation),
        }
    )


def sse_text_start(text_id: str | None = None) -> tuple[str, AssistantStreamEvent]:
    resolved = text_id or f"text-{uuid.uuid4().hex[:12]}"
    return resolved, _sse({"type": "text-start", "id": resolved})


def sse_text_delta(text_id: str, delta: str) -> AssistantStreamEvent:
    return _sse({"type": "text-delta", "id": text_id, "delta": delta})


def sse_text_end(text_id: str) -> AssistantStreamEvent:
    return _sse({"type": "text-end", "id": text_id})


def assistant_event_to_sse_line(event: AssistantStreamEvent) -> str:
    return f"data: {json.dumps({'type': event.sse_type, **event.payload}, separators=(',', ':'))}\n\n"


def chunk_text_deltas(text: str, *, size: int = 24) -> list[str]:
    cleaned = text or ""
    if not cleaned:
        return [""]
    return [cleaned[i : i + size] for i in range(0, len(cleaned), size)]
