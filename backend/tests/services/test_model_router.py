from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

import app.services.model_router as model_router_module
from app.services.model_router import ModelRouter, TaskType, get_model_router


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
        assert router._resolve_model(TaskType.CLASSIFICATION) == "gpt-4o-mini"  # noqa: SLF001
        assert router._resolve_model(TaskType.WORKFLOW_PLANNING) == "claude-3-5-sonnet-20241022"  # noqa: SLF001

    def test_provider_detection(self, router: ModelRouter):
        assert router._provider_for_model("gpt-4o-mini") == "openai"  # noqa: SLF001
        assert router._provider_for_model("claude-3-5-sonnet") == "anthropic"  # noqa: SLF001
        assert router._provider_for_model("gemini-1.5-pro") == "google"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_complete_openai(self, router: ModelRouter):
        router._openai = AsyncMock()  # noqa: SLF001
        router._openai.chat.completions.create = AsyncMock(return_value=_mock_openai_content("hello"))  # noqa: SLF001
        with patch.object(router, "_log_model_call", AsyncMock()):
            response = await router.complete(task_type=TaskType.CLASSIFICATION, prompt="Classify me")
        assert response.provider == "openai"
        assert response.model == "gpt-4o-mini"
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

    def test_singleton_pattern(self):
        model_router_module._model_router_singleton = None
        fake_settings = SimpleNamespace(
            openai_api_key="sk-test",
            anthropic_api_key="",
            google_api_key="",
            default_fast_model="gpt-4o-mini",
            default_reasoning_model="gpt-4o",
        )
        with patch("app.services.model_router.get_settings", return_value=fake_settings):
            router1 = get_model_router()
            router2 = get_model_router()
        assert router1 is router2
