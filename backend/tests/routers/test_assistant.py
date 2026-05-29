"""Tests for the governed assistant streaming endpoint (/api/assistant/chat)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.routers.assistant as assistant_module
from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.main import app


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


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _authenticate(org_id: str = "org-1", settings: Settings | None = None) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: settings or _settings()


def _mock_completion(monkeypatch, content: str = "answer text") -> AsyncMock:
    router = MagicMock()
    response = MagicMock()
    response.content = content
    router.complete = AsyncMock(return_value=response)
    monkeypatch.setattr(assistant_module, "get_model_router", lambda: router)
    return router.complete


async def test_unauthenticated_request_returns_401(async_client):
    resp = await async_client.post(
        "/api/assistant/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


async def test_authenticated_request_returns_streaming_response(async_client, monkeypatch):
    _authenticate(org_id="org-1")
    monkeypatch.setattr(assistant_module, "_run_tools", AsyncMock(return_value=[]))
    _mock_completion(monkeypatch, content="hello-answer")

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hello"}], "org_id": "org-1", "tools": []},
    )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert resp.headers.get("x-vercel-ai-ui-message-stream") == "v1"
    body = resp.text
    assert "hello-answer" in body
    assert "data: [DONE]" in body
    assert '"type":"text-delta"' in body


async def test_wrong_org_id_returns_403(async_client, monkeypatch):
    _authenticate(org_id="org-1")
    _mock_completion(monkeypatch)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hi"}], "org_id": "org-2"},
    )
    assert resp.status_code == 403


async def test_killswitch_active_returns_503(async_client, monkeypatch):
    _authenticate(org_id="org-1", settings=_settings(disable_ai=True))
    completion = _mock_completion(monkeypatch)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hi"}], "org_id": "org-1"},
    )
    assert resp.status_code == 503
    # Killswitch must short-circuit before any model spend.
    completion.assert_not_called()


async def test_tool_results_are_fenced_before_model_injection(async_client, monkeypatch):
    _authenticate(org_id="org-1")

    sentinel = "SENTINEL_TOOL_DATA"
    fake_tools = [
        {
            "name": "knowledge_base",
            "displayName": "searchKnowledgeBase",
            "input": {"query": "q"},
            "output": {"results": [{"title": "Doc", "snippet": sentinel, "relevance": 0.9}], "totalResults": 1},
        }
    ]
    monkeypatch.setattr(assistant_module, "_run_tools", AsyncMock(return_value=fake_tools))

    fence_calls: list[str] = []
    real_fence = assistant_module.fence_untrusted

    def spy_fence(text: str) -> str:
        fence_calls.append(text)
        return real_fence(text)

    monkeypatch.setattr(assistant_module, "fence_untrusted", spy_fence)

    completion = _mock_completion(monkeypatch, content="ok")

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hi"}], "org_id": "org-1", "tools": ["knowledge_base"]},
    )

    assert resp.status_code == 200
    # fence_untrusted was called with the tool output (containing the sentinel).
    assert any(sentinel in call for call in fence_calls), "tool output was not fenced before model injection"

    # And the fenced content actually reached the model context.
    completion.assert_awaited_once()
    _, kwargs = completion.call_args
    context_blob = "".join(msg.get("content", "") for msg in (kwargs.get("context") or []))
    assert sentinel in context_blob
    assert "<untrusted_input>" in context_blob
