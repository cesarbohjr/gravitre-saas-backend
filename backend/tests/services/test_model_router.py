from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

import app.services.model_router as model_router_module
from app.config import MODEL_TIERS, TASK_COMPLEXITY
from app.services.assistant_mode import MODE_DEFAULT_MODELS, resolve_assistant_model
from app.services.model_router import ModelRouter, PreparedStream, TaskType, get_model_router
from app.services.providers.failover import build_priority
from app.services.providers.base import CompletionOptions, ProviderResponse, StreamChunk


class _StructuredOut(BaseModel):
    category: str
    confidence: float


def _mock_openai_content(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


class TestModelRouter:
    @pytest.fixture
    def router(self, mock_settings) -> ModelRouter:
        return ModelRouter(settings=mock_settings)

    def test_task_model_resolution(self, router: ModelRouter):
        # Tiered routing (OpenAI tier): low -> gpt-5.4-mini, high -> gpt-5.5.
        assert router._resolve_model(TaskType.CLASSIFICATION) == "gpt-5.4-mini"  # noqa: SLF001
        assert router._resolve_model(TaskType.WORKFLOW_PLANNING) == "gpt-5.5"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_complete_openai(self, router: ModelRouter):
        router._openai = AsyncMock()  # noqa: SLF001
        router._openai.chat.completions.create = AsyncMock(return_value=_mock_openai_content("hello"))  # noqa: SLF001
        with patch.object(router, "_log_model_call", AsyncMock()):
            response = await router.complete(task_type=TaskType.WORKFLOW_PLANNING, prompt="Plan this")
        assert response.provider == "openai"
        assert response.model == "gpt-5.5"
        assert response.content == "hello"
        assert response.cache_hit is False

    @pytest.mark.asyncio
    async def test_complete_cache_hit(self, router: ModelRouter):
        router._openai = AsyncMock()  # noqa: SLF001
        router._openai.chat.completions.create = AsyncMock(return_value=_mock_openai_content("cached result"))  # noqa: SLF001
        with patch.object(router, "_log_model_call", AsyncMock()):
            first = await router.complete(task_type=TaskType.CLASSIFICATION, prompt="same", use_cache=True)
            second = await router.complete(task_type=TaskType.CLASSIFICATION, prompt="same", use_cache=True)
        assert first.content == "cached result"
        assert second.cache_hit is True
        assert router._openai.chat.completions.create.call_count == 1  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_complete_structured_output(self, router: ModelRouter):
        router._openai = AsyncMock()  # noqa: SLF001
        router._openai.chat.completions.create = AsyncMock(  # noqa: SLF001
            return_value=_mock_openai_content('{"category":"spam","confidence":0.95}')
        )
        with patch.object(router, "_log_model_call", AsyncMock()):
            response = await router.complete(
                task_type=TaskType.CLASSIFICATION,
                prompt="Classify this email",
                response_format=_StructuredOut,
            )
        assert response.parsed is not None
        assert response.parsed["category"] == "spam"
        assert abs(float(response.parsed["confidence"]) - 0.95) < 1e-6

    @pytest.mark.asyncio
    async def test_retry_backoff(self, router: ModelRouter):
        router._openai = AsyncMock()  # noqa: SLF001
        router._openai.chat.completions.create = AsyncMock(  # noqa: SLF001
            side_effect=[RuntimeError("temporary"), _mock_openai_content("ok")]
        )
        with patch.object(router, "_log_model_call", AsyncMock()):
            response = await router.complete(task_type=TaskType.CLASSIFICATION, prompt="retry")
        assert response.content == "ok"
        assert router._openai.chat.completions.create.call_count == 2  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_stream_yields_deltas_then_final_response(self, router: ModelRouter):
        prepared = PreparedStream(
            task_type=TaskType.RAG_ANSWERING,
            org_id="org-1",
            prompt="hello",
            system_prompt="sys",
            messages=[{"role": "user", "content": "hello"}],
            priority=[("openai", "gpt-5.5")],
            options=CompletionOptions(),
            model="gpt-5.5",
        )

        async def fake_failover_stream(*_args, **_kwargs):
            yield StreamChunk(delta="hel")
            yield StreamChunk(delta="lo")
            yield StreamChunk(
                done=True,
                response=ProviderResponse(
                    content="hello",
                    provider_used="openai",
                    model_used="gpt-5.5",
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                    latency_ms=50.0,
                ),
            )

        with (
            patch("app.services.model_router.run_failover_stream", fake_failover_stream),
            patch("app.services.model_router.moderate_output", AsyncMock()),
            patch.object(router, "_log_model_call", AsyncMock(return_value="mc-stream-1")),
            patch.object(router, "_log_guardrail_event", AsyncMock()),
        ):
            events = [event async for event in router.stream(prepared)]

        assert [event.delta for event in events if event.delta] == ["hel", "lo"]
        final = events[-1].response
        assert final is not None
        assert final.content == "hello"
        assert final.model_call_id == "mc-stream-1"

    def test_singleton_pattern(self):
        model_router_module._model_router_singleton = None
        fake_settings = SimpleNamespace(
            openai_api_key="sk-test",
            anthropic_api_key="",
            google_api_key="",
        )
        with patch("app.services.model_router.get_settings", return_value=fake_settings):
            router1 = get_model_router()
            router2 = get_model_router()
        assert router1 is router2


def test_model_router_returns_updated_model_per_tier():
    router = ModelRouter(
        settings=SimpleNamespace(openai_api_key="sk-test", anthropic_api_key="", google_api_key="")
    )
    assert router._resolve_model(TaskType.CLASSIFICATION) == MODEL_TIERS["low"]["openai"]  # noqa: SLF001
    assert router._resolve_model(TaskType.RAG_ANSWERING) == MODEL_TIERS["medium"]["openai"]  # noqa: SLF001
    assert router._resolve_model(TaskType.WORKFLOW_PLANNING) == MODEL_TIERS["high"]["openai"]  # noqa: SLF001
    assert MODEL_TIERS["low"]["openai"] == "gpt-5.4-mini"
    assert MODEL_TIERS["medium"]["openai"] == "gpt-5.5"
    assert MODEL_TIERS["high"]["openai"] == "gpt-5.5"


def test_existing_tier_routing_logic_unchanged_in_structure():
    """Config-only model IDs; tier dispatch and mode mapping architecture unchanged."""
    assert set(MODEL_TIERS) == {"low", "medium", "high"}
    for tier in MODEL_TIERS:
        assert set(MODEL_TIERS[tier]) == {"openai", "anthropic", "gemini"}

    assert TASK_COMPLEXITY["summarization"] == "low"
    assert TASK_COMPLEXITY["rag_answering"] == "medium"
    assert TASK_COMPLEXITY["workflow_planning"] == "high"

    low_priority = build_priority("auto", "low")
    high_priority = build_priority("auto", "high")
    assert low_priority[0] == ("openai", MODEL_TIERS["low"]["openai"])
    assert high_priority[0] == ("anthropic", MODEL_TIERS["high"]["anthropic"])

    fast_model, fast_task = resolve_assistant_model("fast", None)
    standard_model, standard_task = resolve_assistant_model("standard", None)
    reasoning_model, reasoning_task = resolve_assistant_model("reasoning", None)
    assert fast_model == MODE_DEFAULT_MODELS["fast"]
    assert standard_model == MODE_DEFAULT_MODELS["standard"]
    assert reasoning_model == MODE_DEFAULT_MODELS["reasoning"]
    assert fast_task.value == "summarization"
    assert standard_task.value == "rag_answering"
    assert reasoning_task.value == "decision_reasoning"
