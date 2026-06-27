"""Tests for assistant chat unified AgentIntelligence streaming pipeline."""
from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.routers.assistant as assistant_module
from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.main import app
from app.operators.assistant_mode_config import mode_includes_tool, resolve_assistant_tool_names
from app.operators.react_engine import ReActResult, ReActStatus
from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.model_router import TaskType


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
    )
    base.update(overrides)
    return Settings(**base)


def _authenticate(org_id: str = "org-1") -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()


async def _fake_stream(**overrides):
    yield AssistantStreamEvent(sse_type="tool-input-available", payload={"toolCallId": "c1", "toolName": "searchKnowledgeBase", "input": {"query": "hi"}})
    yield AssistantStreamEvent(sse_type="tool-output-available", payload={"toolCallId": "c1", "output": {"totalResults": 1}})
    yield AssistantStreamEvent(sse_type="text-start", payload={"id": "t1"})
    yield AssistantStreamEvent(sse_type="text-delta", payload={"id": "t1", "delta": "hello "})
    yield AssistantStreamEvent(sse_type="text-delta", payload={"id": "t1", "delta": "world"})
    yield AssistantStreamEvent(sse_type="text-end", payload={"id": "t1"})
    yield AssistantStreamComplete(
        full_content=overrides.get("full_content", "hello world"),
        tool_results=overrides.get(
            "tool_results",
            [
                {
                    "name": "knowledge_base",
                    "displayName": "searchKnowledgeBase",
                    "input": {"query": "hi"},
                    "output": {"totalResults": 1},
                }
            ],
        ),
        react_result=ReActResult(status=ReActStatus.COMPLETED, answer="hello world"),
        model="gpt-5.5",
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _mock_assistant_helpers(monkeypatch):
    assistant_module._RESPONSE_CACHE.clear()
    monkeypatch.setattr(
        assistant_module,
        "_build_assistant_system_prompt",
        lambda *args, **kwargs: "test system prompt",
    )
    monkeypatch.setattr(assistant_module, "_persist_conversation_turn", lambda *args, **kwargs: None)
    monkeypatch.setattr(assistant_module, "_generate_followup_suggestions", AsyncMock(return_value=["Next step A", "Next step B", "Next step C"]))
    monkeypatch.setattr(assistant_module, "_record_assistant_billing", AsyncMock())


def _mock_prepare_stream(monkeypatch):
    router = MagicMock()
    router.prepare_stream = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(assistant_module, "get_model_router", lambda: router)
    return router


async def test_chat_endpoint_uses_agent_intelligence_streaming(async_client, monkeypatch):
    _authenticate()
    _mock_prepare_stream(monkeypatch)
    intelligence = MagicMock()
    intelligence.execute_task_streaming = _fake_stream
    monkeypatch.setattr(assistant_module, "get_agent_intelligence", lambda: intelligence)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hello"}], "org_id": "org-1", "tools": []},
    )

    assert resp.status_code == 200
    body = resp.text
    assert "hello " in body
    assert "world" in body
    assert '"type":"data-suggestions"' in body
    assert "data: [DONE]" in body


def test_standard_mode_includes_web_search_tool():
    tools = resolve_assistant_tool_names("standard", None)
    assert "search_web" in tools


def test_fast_mode_excludes_web_search_tool():
    tools = resolve_assistant_tool_names("fast", None)
    assert "search_web" not in tools


async def test_sse_event_types_match_existing_contract(async_client, monkeypatch):
    _authenticate()
    _mock_prepare_stream(monkeypatch)
    intelligence = MagicMock()
    intelligence.execute_task_streaming = _fake_stream
    monkeypatch.setattr(assistant_module, "get_agent_intelligence", lambda: intelligence)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hello"}], "org_id": "org-1"},
    )
    body = resp.text
    for event_type in (
        "start",
        "start-step",
        "tool-input-available",
        "tool-output-available",
        "text-start",
        "text-delta",
        "text-end",
        "data-suggestions",
        "finish-step",
        "finish",
    ):
        assert f'"type":"{event_type}"' in body
    assert "data: [DONE]" in body


async def test_tool_chip_summary_format_unchanged(async_client, monkeypatch):
    _authenticate()
    _mock_prepare_stream(monkeypatch)
    intelligence = MagicMock()
    intelligence.execute_task_streaming = _fake_stream
    monkeypatch.setattr(assistant_module, "get_agent_intelligence", lambda: intelligence)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hello"}], "org_id": "org-1"},
    )
    assert '"toolName":"searchKnowledgeBase"' in resp.text
    assert '"totalResults":1' in resp.text


async def test_conversation_persistence_still_works(async_client, monkeypatch):
    _authenticate()
    _mock_prepare_stream(monkeypatch)
    intelligence = MagicMock()
    intelligence.execute_task_streaming = _fake_stream
    monkeypatch.setattr(assistant_module, "get_agent_intelligence", lambda: intelligence)
    persist = MagicMock(return_value="conv-1")
    monkeypatch.setattr(assistant_module, "_persist_conversation_turn", persist)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hello"}], "org_id": "org-1", "conversation_id": "conv-1"},
    )
    resp.text
    persist.assert_called_once()
    assert persist.call_args.kwargs["assistant_text"] == "hello world"


async def test_followup_suggestions_still_generated(async_client, monkeypatch):
    _authenticate()
    _mock_prepare_stream(monkeypatch)
    intelligence = MagicMock()
    intelligence.execute_task_streaming = _fake_stream
    monkeypatch.setattr(assistant_module, "get_agent_intelligence", lambda: intelligence)
    suggest = AsyncMock(return_value=["Ask about agents", "Check connectors", "Review workflows"])
    monkeypatch.setattr(assistant_module, "_generate_followup_suggestions", suggest)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hello"}], "org_id": "org-1"},
    )
    body = resp.text
    resp.text
    suggest.assert_awaited_once()
    assert "Ask about agents" in body


def test_react_loop_not_duplicated():
    from app.operators import react_engine as react_module

    source = open(react_module.__file__, encoding="utf-8").read()
    assert source.count("async def _react_loop(") == 1
    assert "async def run(" in source
    assert "async def run_streaming(" in source
    assert "run_legacy_removed" not in source


def test_mode_includes_search_web_for_standard_backend_default():
    assert mode_includes_tool("standard", "search_web")


async def test_chat_omitted_tools_uses_mode_config_defaults(async_client, monkeypatch):
    """When the client omits `tools`, backend MODE_CONFIG selects tools for `mode`."""
    _authenticate()
    _mock_prepare_stream(monkeypatch)
    captured: dict[str, object] = {}

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        async for event in _fake_stream():
            yield event

    intelligence = MagicMock()
    intelligence.execute_task_streaming = fake_execute
    monkeypatch.setattr(assistant_module, "get_agent_intelligence", lambda: intelligence)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "org_id": "org-1",
            "mode": "standard",
        },
    )

    assert resp.status_code == 200
    resp.text
    assert captured.get("requested_tools") is None
    assert captured.get("mode") == "standard"
    assert "search_web" in resolve_assistant_tool_names("standard", captured.get("requested_tools"))
