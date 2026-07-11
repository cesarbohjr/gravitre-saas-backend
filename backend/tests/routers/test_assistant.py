"""Tests for the governed assistant streaming endpoint (/api/assistant/chat)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.routers.assistant as assistant_module
from app.services import assistant_tools as tools_module
from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.main import app
from app.operators.react_engine import ReActResult, ReActStatus
from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.model_router import ModelResponse, PreparedStream


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
    assistant_module._RESPONSE_CACHE.clear()
    monkeypatch.setattr(
        assistant_module,
        "_build_assistant_system_prompt",
        lambda *args, **kwargs: "test system prompt",
    )
    monkeypatch.setattr(assistant_module, "_persist_conversation_turn", lambda *args, **kwargs: None)
    monkeypatch.setattr(assistant_module, "_generate_followup_suggestions", AsyncMock(return_value=[]))


def _authenticate(org_id: str = "org-1", settings: Settings | None = None) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: settings or _settings()


def _mock_prepare_stream_guardrails(monkeypatch) -> MagicMock:
    router = MagicMock()
    router.prepare_stream = AsyncMock(return_value=MagicMock(spec=PreparedStream))
    monkeypatch.setattr(assistant_module, "get_model_router", lambda: router)
    return router


def _mock_agent_intelligence_stream(monkeypatch, content: str = "answer text", **overrides) -> MagicMock:
    captured: dict[str, object] = {}

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        yield AssistantStreamEvent(sse_type="text-start", payload={"id": "t1"})
        yield AssistantStreamEvent(sse_type="text-delta", payload={"id": "t1", "delta": content})
        yield AssistantStreamEvent(sse_type="text-end", payload={"id": "t1"})
        yield AssistantStreamComplete(
            full_content=content,
            tool_results=overrides.get("tool_results", []),
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer=content),
            model=overrides.get("model", "gpt-5.5"),
        )

    intelligence = MagicMock()
    intelligence.execute_task_streaming = fake_execute
    intelligence._captured = captured
    monkeypatch.setattr(assistant_module, "get_agent_intelligence", lambda: intelligence)
    return intelligence


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
    _mock_prepare_stream_guardrails(monkeypatch)
    _mock_agent_intelligence_stream(monkeypatch, content="hello-answer")

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
    _mock_prepare_stream_guardrails(monkeypatch)
    _mock_agent_intelligence_stream(monkeypatch, content="ok")

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hi"}], "org_id": "org-2"},
    )
    assert resp.status_code == 200
    assert "ok" in resp.text


async def test_killswitch_active_returns_503(async_client, monkeypatch):
    _authenticate(org_id="org-1", settings=_settings(disable_ai=True))
    router = _mock_prepare_stream_guardrails(monkeypatch)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hi"}], "org_id": "org-1"},
    )
    assert resp.status_code == 503
    # Killswitch must short-circuit before any model spend.
    router.prepare_stream.assert_not_called()


async def test_tool_results_are_fenced_before_model_injection(monkeypatch):
    """ReAct loop fences task input via fence_untrusted before model calls."""
    from app.operators import react_engine as react_module

    fence_calls: list[str] = []
    real_fence = react_module.fence_untrusted

    def spy_fence(text: str) -> str:
        fence_calls.append(text)
        return real_fence(text)

    monkeypatch.setattr(react_module, "fence_untrusted", spy_fence)
    monkeypatch.setattr(react_module, "moderate_input", AsyncMock())

    engine = react_module.ReActEngine(settings=_settings(), registry=MagicMock())
    engine.registry.get_tools_for_agent = MagicMock(return_value=[])
    engine.registry.get_available_tools = AsyncMock(return_value=[])
    engine.registry.list_connected_integrations = MagicMock(return_value=[])

    sentinel = "SENTINEL_TOOL_DATA"
    ctx = MagicMock()
    ctx.client = MagicMock()
    ctx.org_id = "org-1"
    ctx.settings = _settings()
    ctx.environment_name = "default"
    ctx.actor_id = "user-1"
    ctx.agent_id = None
    ctx.task_id = None
    ctx.run_id = None

    fake_reasoning = AsyncMock(
        return_value=react_module.ReActResult(status=react_module.ReActStatus.COMPLETED, answer="ok")
    )
    monkeypatch.setattr(engine, "_run_reasoning_only", fake_reasoning)

    await engine.run(ctx=ctx, task=sentinel, system_prompt="sys", connected_integrations=[])

    assert any(sentinel in call for call in fence_calls)
    passed_messages = fake_reasoning.await_args.kwargs.get("messages") or fake_reasoning.await_args.args[1]
    user_content = next(m["content"] for m in passed_messages if m.get("role") == "user")
    assert "<untrusted_input>" in user_content


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
    _mock_prepare_stream_guardrails(monkeypatch)
    _mock_agent_intelligence_stream(monkeypatch, content="hello billing text")

    record_mock = AsyncMock()
    monkeypatch.setattr(assistant_module, "_record_assistant_billing", record_mock)

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={"messages": [{"role": "user", "content": "hello"}], "org_id": "org-1", "tools": []},
    )
    assert resp.status_code == 200
    resp.text  # drain stream so billing/background tasks are scheduled
    for coro in capture_background_tasks:
        await coro
    record_mock.assert_awaited_once()
    args = record_mock.call_args[0]
    assert args[1] == "org-1"
    assert args[2].input_tokens >= 1
    assert args[2].output_tokens >= 1


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


async def test_agent_chat_passes_agent_id_to_tools(async_client, monkeypatch):
    _authenticate(org_id="org-1")
    _mock_prepare_stream_guardrails(monkeypatch)
    intelligence = _mock_agent_intelligence_stream(monkeypatch, content="scoped")

    resp = await async_client.post(
        "/api/assistant/chat",
        headers={"Authorization": "Bearer token"},
        json={
            "messages": [{"role": "user", "content": "pipeline status"}],
            "org_id": "org-1",
            "agent_id": "agent-revops",
            "mode": "agent",
            "tools": ["knowledge_base", "agent_status"],
        },
    )

    assert resp.status_code == 200
    resp.text
    assert intelligence._captured.get("agent_id") == "agent-revops"


def test_resolve_base_system_prompt_uses_agent_persona(monkeypatch):
    agent = {
        "id": "agent-revops",
        "name": "RevOps Analyst",
        "role": "Revenue Operations",
        "department": "Sales",
        "description": "Pipeline hygiene specialist",
        "status": "active",
        "systems": ["hubspot", "salesforce"],
    }
    monkeypatch.setattr(
        assistant_module,
        "get_supabase_client",
        lambda _s: object(),
    )
    monkeypatch.setattr(
        "app.operators.agent_intelligence.resolve_agent_record",
        lambda _c, _o, agent_id, **kwargs: agent if agent_id == "agent-revops" else None,
    )

    prompt = assistant_module._resolve_base_system_prompt(
        _settings(),
        "org-1",
        "agent-revops",
        org_context={"connectedIntegrations": ["hubspot"]},
    )

    assert "RevOps Analyst" in prompt
    assert prompt != assistant_module.ASSISTANT_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_tool_knowledge_base_uses_agent_scope(monkeypatch):
    captured: dict[str, object] = {}

    class FakeBundle:
        rag_sources = [
            {"id": "c1", "source": "playbook", "content": "ICP notes", "score": 0.9},
        ]
        memory_context = {"memories": [{"content": "prefers concise summaries", "score": 0.8}]}
        metrics = {"embedding_method": "openai"}

    async def fake_retrieve(**kwargs):
        captured.update(kwargs)
        return FakeBundle()

    fake_service = MagicMock()
    fake_service.retrieve = fake_retrieve
    monkeypatch.setattr(
        "app.services.unified_retrieval_service.get_unified_retrieval_service",
        lambda: fake_service,
    )
    monkeypatch.setattr(
        tools_module,
        "get_supabase_client",
        lambda _s: MagicMock(),
    )

    output = await tools_module.tool_knowledge_base(
        "org-1",
        "pipeline risks",
        _settings(),
        agent_id="agent-revops",
    )

    assert captured.get("org_id") == "org-1"
    assert captured.get("query") == "pipeline risks"
    assert captured.get("agent") == {"id": "agent-revops"}
    assert captured.get("scopes").knowledge is True
    assert captured.get("scopes").org_context is False
    assert captured.get("scopes").agent_memory is True
    assert output["scope"] == "agent"
    assert output["agentId"] == "agent-revops"
    assert output["sources"][0]["title"] == "playbook"
    assert output["memoryHitCount"] == 1


async def test_assistant_org_context_returns_production_connectors(async_client, monkeypatch):
    _authenticate(org_id="org-1")
    snapshot = {
        "agents": [],
        "workflows": [],
        "integrations": [{"id": "c1", "type": "hubspot", "status": "connected"}],
        "counts": {"agents": 0, "workflows": 0, "connectedIntegrations": 1},
        "connectedIntegrations": ["hubspot"],
    }
    service = MagicMock()
    service.get_snapshot.return_value = snapshot
    monkeypatch.setattr(assistant_module, "get_org_context_service", lambda: service)
    monkeypatch.setattr(assistant_module, "get_supabase_client", lambda _s: MagicMock())

    resp = await async_client.get(
        "/api/assistant/org-context",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"]["connectors"] == 1
    assert body["connectors"][0]["type"] == "hubspot"
    service.get_snapshot.assert_called_once()
    assert service.get_snapshot.call_args.kwargs["environment_name"] == "production"


def test_response_cache_skips_confirmations_and_scopes_by_conversation():
    """Claim 4: org-scoped 'yes' cache must not skip pending connector confirm."""
    assert assistant_module._response_cache_eligible("In Apollo, create a contact list.")
    assert not assistant_module._response_cache_eligible("yes")
    assert not assistant_module._response_cache_eligible("no")
    assert not assistant_module._response_cache_eligible("confirm")
    k1 = assistant_module._response_cache_key("org", "yes", "conv-a")
    k2 = assistant_module._response_cache_key("org", "yes", "conv-b")
    assert k1 != k2
