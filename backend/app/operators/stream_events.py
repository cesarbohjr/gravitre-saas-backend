"""Streaming event types for assistant SSE and ReAct progress."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReActStreamEvent:
    kind: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_call_id: str | None = None
    result: dict[str, Any] | None = None
    content: str | None = None
    react_result: Any | None = None


@dataclass(frozen=True)
class AssistantStreamEvent:
    """Maps to AI SDK UI message stream protocol events in assistant router."""

    sse_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AssistantStreamComplete:
    """Terminal payload for assistant streaming — not emitted as SSE."""

    full_content: str
    tool_results: list[dict[str, Any]]
    react_result: Any
    model: str
    summary: str | None = None
    summary_updated: bool = False
    message_id: str | None = None
    confidence: dict[str, Any] | None = None
    answer_explanation: str | None = None
    validation: dict[str, Any] | None = None
    conflicts: list[dict[str, Any]] | None = None
    refined_query: str | None = None
    dialogue_mode: str | None = None
    persona_key: str | None = None
    proactive_suggestions: list[str] | None = None
    task_state: dict[str, Any] | None = None
    execution_result: dict[str, Any] | None = None
    pending_task: dict[str, Any] | None = None
