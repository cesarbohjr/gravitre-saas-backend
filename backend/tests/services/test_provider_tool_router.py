"""Unit tests for multi-provider tool-calling router."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.providers.provider_tool_router import (
    openai_messages_to_anthropic,
    openai_messages_to_gemini_contents,
    openai_tools_to_anthropic,
    resolve_provider_for_model,
)
from app.services.providers.tool_completion import make_openai_compatible_response, ToolCallSpec, ToolCompletionResult


def test_resolve_provider_for_model_known_agents_hub_ids():
    assert resolve_provider_for_model("claude-sonnet-4-6") == "anthropic"
    assert resolve_provider_for_model("gemini-2.5-flash") == "gemini"
    assert resolve_provider_for_model("gpt-5.5") == "openai"


def test_openai_tools_to_anthropic_uses_input_schema():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "hubspot_lists_create",
                "description": "Create a list",
                "parameters": {"type": "object", "properties": {"name": {"type": "string"}}},
            },
        }
    ]
    native = openai_tools_to_anthropic(tools)
    assert native[0]["name"] == "hubspot_lists_create"
    assert native[0]["input_schema"]["properties"]["name"]["type"] == "string"
    assert "parameters" not in native[0]


def test_openai_messages_to_anthropic_tool_round_trip_shape():
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Create a list"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "hubspot_lists_create", "arguments": '{"name":"A"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": '{"success": true}'},
    ]
    system, convo = openai_messages_to_anthropic(messages)
    assert system == "You are helpful."
    assert convo[1]["role"] == "assistant"
    assert convo[1]["content"][0]["type"] == "tool_use"
    assert convo[1]["content"][0]["input"] == {"name": "A"}
    assert convo[2]["role"] == "user"
    assert convo[2]["content"][0]["type"] == "tool_result"
    assert convo[2]["content"][0]["tool_use_id"] == "call_1"


def test_openai_messages_to_gemini_function_response_uses_tool_name():
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc1",
                    "function": {"name": "search_catalog_tools", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "tc1", "content": "found 2 tools"},
    ]
    contents = openai_messages_to_gemini_contents(messages)
    fn_resp = contents[-1]["parts"][0]["function_response"]
    assert fn_resp["name"] == "search_catalog_tools"
    assert "found 2 tools" in str(fn_resp["response"]["content"])


def test_make_openai_compatible_response_tool_calls():
    result = ToolCompletionResult(
        content="done",
        tool_calls=[ToolCallSpec(id="x", name="apollo_lists_create", arguments='{"a":1}')],
    )
    resp = make_openai_compatible_response(result)
    assert resp.choices[0].message.tool_calls[0].function.name == "apollo_lists_create"


@pytest.mark.asyncio
async def test_complete_with_tools_dispatches_anthropic(monkeypatch):
    from app.services.providers import provider_tool_router as ptr

    async def _fake_anthropic(**kwargs):
        assert kwargs["model"] == "claude-sonnet-4-6"
        raw = kwargs["tools"][0]
        fn = raw.get("function") if isinstance(raw.get("function"), dict) else raw
        assert fn.get("name") == "web_search"
        return ToolCompletionResult(
            content=None,
            tool_calls=[ToolCallSpec(id="tu_1", name="web_search", arguments='{"q":"x"}')],
            prompt_tokens=1,
            completion_tokens=2,
        )

    monkeypatch.setattr(ptr, "_complete_anthropic_with_tools", _fake_anthropic)
    router = MagicMock()
    router.settings = SimpleNamespace(anthropic_api_key="sk-test", gemini_api_key="", openai_api_key="")
    from app.services.narrowed_tools import mark_narrowed

    tools = mark_narrowed(
        [{"type": "function", "function": {"name": "web_search", "parameters": {"type": "object"}}}]
    )
    resp = await ptr.complete_with_tools(
        router,
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "search"}],
        tools=tools,
    )
    assert resp.choices[0].message.tool_calls[0].function.name == "web_search"


@pytest.mark.asyncio
async def test_complete_with_tools_blocks_unnarrowed():
    from app.services.providers.provider_tool_router import complete_with_tools

    router = MagicMock()
    plain = [{"type": "function", "function": {"name": "x", "parameters": {}}}]
    with pytest.raises(RuntimeError, match="unnarrowed_tool_attach_blocked"):
        await complete_with_tools(
            router,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            tools=plain,
        )
