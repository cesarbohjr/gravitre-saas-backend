"""Tests for the governed assistant streaming endpoint (/api/assistant/chat)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.routers.assistant as assistant_module
from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.main import app
from app.services.model_router import ModelResponse, ModelStreamEvent, PreparedStream


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


@pytest.fixture(autouse=True)
def _mock_assistant_dependencies(monkeypatch):
    """Keep assistant router tests offline (no Supabase org-context fetch)."""
    monkeypatch.setattr(
        assistant_module,
        "_build_assistant_system_prompt",
        lambda *args, **kwargs: "test system prompt",
    )
    monkeypatch.setattr(assistant_module, "_persist_conversation_turn", lambda *args, **kwargs: None)


def _authenticate(org_id: str = "org-1", settings: Settings | None = None) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: settings or _settings()


def _mock_stream(monkeypatch, content: str = "answer text", **result_overrides) -> MagicMock:
    router = MagicMock()
    response = ModelResponse(
        provider=result_overrides.pop("provider", "openai"),
        model=result_overrides.pop("model", "gpt-5.5"),
        content=content,
        input_tokens=result_overrides.pop("input_tokens", 100),
        output_tokens=result_overrides.pop("output_tokens", 50),
        latency_ms=result_overrides.pop("latency_ms", 120),
        cost_usd=result_overrides.pop("cost_usd", 0.001),
        model_call_id=result_overrides.pop("model_call_id", "mc-123"),
        **result_overrides,
    )
    prepared = MagicMock(spec=PreparedStream)

    async def fake_stream(_prepared):
        yield ModelStreamEvent(delta=content)
        yield ModelStreamEvent(response=response)

    router.prepare_stream = AsyncMock(return_value=prepared)
    router.stream = fake_stream
    monkeypatch.setattr(assistant_module, "get_model_router", lambda: router)
    return router


@pytest.fixture
def capture_background_tasks(monkeypatch):
    """Collect asyncio.create_task coroutines so tests can await them."""
    pending: list = []

    def _capture(coro):
        pending.append(coro)
        return MagicMock()

    monkeypatch.setattr(assistant_module.asyncio, "create_task", _capture)
    return pending


async def test_unauthenticated_request_returns_401(async_client):
    resp = await async_client.post(
        "/api/assistant/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


async def test_authenticated_request_returns_streaming_response(async_client, monkeypatch):
    _authenticate(org_id="org-1")
    monkeypatch.setattr(assistant_module, "_run_tools", AsyncMock(return_value=[]))
    _mock_stream(monkeypatch, content="hello-answer")

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


async def test_stale_body_org_id_uses_validated_org(async_client, monkeypatch):
    """Client body org_id is a hint only; JWT-validated org wins (no 403)."""
    _authenticate(org_id="org-1")
    monkeypatch.setattr(assistant_module, "_run_tools", AsyncMock(return_value=[]))
    _mock_stream(monkeypatch, content="ok")

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hi"}], "org_id": "org-2"},
    )
    assert resp.status_code == 200
    assert "ok" in resp.text


async def test_killswitch_active_returns_503(async_client, monkeypatch):
    _authenticate(org_id="org-1", settings=_settings(disable_ai=True))
    router = _mock_stream(monkeypatch)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hi"}], "org_id": "org-1"},
    )
    assert resp.status_code == 503
    # Killswitch must short-circuit before any model spend.
    router.prepare_stream.assert_not_called()


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

    router = _mock_stream(monkeypatch, content="ok")

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hi"}], "org_id": "org-1", "tools": ["knowledge_base"]},
    )

    assert resp.status_code == 200
    # fence_untrusted was called with the tool output (containing the sentinel).
    assert any(sentinel in call for call in fence_calls), "tool output was not fenced before model injection"

    # And the fenced content actually reached the model context.
    router.prepare_stream.assert_awaited_once()
    _, kwargs = router.prepare_stream.call_args
    context_blob = "".join(msg.get("content", "") for msg in (kwargs.get("context") or []))
    assert sentinel in context_blob
    assert "<untrusted_input>" in context_blob


async def test_killswitch_logs_guardrail_event(async_client, monkeypatch, capture_background_tasks):
    _authenticate(org_id="org-1", settings=_settings(disable_ai=True))
    log_mock = AsyncMock()
    monkeypatch.setattr(assistant_module, "_log_assistant_guardrail_event", log_mock)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hi"}], "org_id": "org-1"},
    )
    assert resp.status_code == 503
    for coro in capture_background_tasks:
        await coro
    log_mock.assert_awaited_once()
    assert log_mock.call_args[0][2] == "killswitch_blocked"


async def test_billing_scheduled_after_success(async_client, monkeypatch, capture_background_tasks):
    _authenticate(org_id="org-1")
    monkeypatch.setattr(assistant_module, "_run_tools", AsyncMock(return_value=[]))
    _mock_stream(monkeypatch, input_tokens=200, output_tokens=80, model_call_id="mc-bill-1")

    record_mock = AsyncMock()
    monkeypatch.setattr(assistant_module, "_record_assistant_billing", record_mock)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hello"}], "org_id": "org-1", "tools": []},
    )
    assert resp.status_code == 200
    for coro in capture_background_tasks:
        await coro
    record_mock.assert_awaited_once()
    args = record_mock.call_args[0]
    assert args[1] == "org-1"
    assert args[2].input_tokens == 200
    assert args[2].output_tokens == 80


async def test_record_assistant_billing_uses_real_tokens(monkeypatch):
    settings = _settings()
    client = MagicMock()
    plan = {"ai_credits_included": 1000}
    apply_mock = MagicMock()
    meta_mock = MagicMock(return_value={"credits": 5, "source": "assistant", "source_id": "mc-1"})

    monkeypatch.setattr(assistant_module, "get_supabase_client", lambda _s: client)
    monkeypatch.setattr(assistant_module, "get_plan_for_org", lambda _c, _o: plan)
    monkeypatch.setattr(assistant_module, "get_current_period", lambda: ("2026-05-01", "2026-05-31"))
    monkeypatch.setattr(assistant_module, "build_ai_usage_metadata_from_tokens", meta_mock)
    monkeypatch.setattr(assistant_module, "apply_usage_with_overage", apply_mock)

    result = ModelResponse(
        provider="openai",
        model="gpt-5.5",
        content="ok",
        input_tokens=1000,
        output_tokens=500,
        latency_ms=50,
        cost_usd=0.01,
        model_call_id="mc-1",
    )
    await assistant_module._record_assistant_billing(settings, "org-1", result)

    meta_mock.assert_called_once_with(1000, 500, "gpt-5.5", "assistant", "mc-1")
    apply_mock.assert_called_once()
    assert apply_mock.call_args.kwargs["metadata"]["source"] == "assistant"


async def test_billing_failure_does_not_raise(monkeypatch):
    settings = _settings()
    log_mock = AsyncMock()
    monkeypatch.setattr(assistant_module, "get_supabase_client", lambda _s: (_ for _ in ()).throw(RuntimeError("db down")))
    monkeypatch.setattr(assistant_module, "_log_assistant_guardrail_event", log_mock)

    result = ModelResponse(
        provider="openai",
        model="gpt-5.5",
        content="ok",
        input_tokens=10,
        output_tokens=5,
        latency_ms=1,
        cost_usd=0.0,
        model_call_id="mc-fail",
    )
    await assistant_module._record_assistant_billing(settings, "org-1", result)
    log_mock.assert_awaited_once()
    assert log_mock.call_args[0][2] == "billing_write_failed"


async def test_billing_idempotency_same_source_id(monkeypatch):
    from app.billing.service import apply_usage_with_overage, build_ai_usage_metadata_from_tokens, get_current_period

    client = MagicMock()
    inserted = []

    def fake_idempotent_insert(_client, table, org_id, payload, key):
        if key in inserted:
            return False
        inserted.append(key)
        return True

    monkeypatch.setattr("app.billing.service._idempotent_insert", fake_idempotent_insert)
    monkeypatch.setattr("app.billing.service._sum_usage", lambda *a, **k: 0)

    plan = {"ai_credits_included": 10000}
    period_start, period_end = get_current_period()
    meta = build_ai_usage_metadata_from_tokens(100, 50, "gpt-5.5", "assistant", "mc-same")
    apply_usage_with_overage(
        client, "org-1", "production", "ai_credits", int(meta["credits"]),
        plan, period_start, period_end, metadata=meta,
    )
    apply_usage_with_overage(
        client, "org-1", "production", "ai_credits", int(meta["credits"]),
        plan, period_start, period_end, metadata=meta,
    )
    assert len(inserted) == 1
