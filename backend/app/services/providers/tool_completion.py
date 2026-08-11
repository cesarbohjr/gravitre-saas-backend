"""Normalized tool-calling completion types (provider-agnostic internal shape)."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any


@dataclass
class ToolCallSpec:
    id: str
    name: str
    arguments: str


@dataclass
class ToolCompletionResult:
    content: str | None
    tool_calls: list[ToolCallSpec] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_response: Any = field(default=None, repr=False)


def make_openai_compatible_response(result: ToolCompletionResult) -> Any:
    """Shape expected by react_engine / unified_turn (OpenAI chat completion layout)."""
    fn_calls: list[Any] = []
    for tc in result.tool_calls:
        if not tc.name:
            continue
        fn_calls.append(
            SimpleNamespace(
                id=tc.id or str(uuid.uuid4()),
                type="function",
                function=SimpleNamespace(
                    name=tc.name,
                    arguments=tc.arguments or "{}",
                ),
            )
        )
    message = SimpleNamespace(
        content=result.content,
        tool_calls=fn_calls or None,
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def parse_json_args(raw: str | dict | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def tool_name_for_call_id(messages: list[dict[str, Any]], call_id: str | None) -> str | None:
    cid = str(call_id or "").strip()
    if not cid:
        return None
    for msg in reversed(messages):
        if str(msg.get("role") or "") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            if str(tc.get("id") or "") == cid:
                fn = tc.get("function") or {}
                name = str(fn.get("name") or "").strip()
                return name or None
    return None
