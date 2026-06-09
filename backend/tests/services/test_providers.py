from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.rag.embedding import embed_with_failover
from app.services.providers.anthropic_adapter import AnthropicAdapter
from app.services.providers.base import (
    CompletionOptions,
    ProviderInvalidResponseError,
    ProviderResponse,
    ProviderUnavailableError,
    extract_system,
)
from app.services.providers.gemini_adapter import GeminiAdapter
from app.services.providers.openai_adapter import OpenAIAdapter


def _openai_resp(content: str, pt: int = 10, ct: int = 5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=pt, completion_tokens=ct),
    )


class TestBaseHelpers:
    def test_extract_system(self):
        system, rest = extract_system(
            [
                {"role": "system", "content": "be nice"},
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ]
        )
        assert system == "be nice"
        assert [m["role"] for m in rest] == ["user", "assistant"]


class TestOpenAIAdapter:
    @pytest.mark.asyncio
    async def test_complete_normalizes_usage(self):
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=_openai_resp("hello", 10, 5))
        adapter = OpenAIAdapter(client_getter=lambda: client, api_key_getter=lambda: "sk")
        r = await adapter.complete([{"role": "user", "content": "hi"}], "gpt-5.5", CompletionOptions())
        assert isinstance(r, ProviderResponse)
        assert r.content == "hello"
        assert (r.prompt_tokens, r.completion_tokens, r.total_tokens) == (10, 5, 15)
        assert r.provider_used == "openai"
        assert r.model_used == "gpt-5.5"

    @pytest.mark.asyncio
    async def test_gpt5_omits_custom_temperature(self):
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=_openai_resp("hello"))
        adapter = OpenAIAdapter(client_getter=lambda: client, api_key_getter=lambda: "sk")
        await adapter.complete(
            [{"role": "user", "content": "hi"}],
            "gpt-5.5",
            CompletionOptions(temperature=0.2),
        )
        kwargs = client.chat.completions.create.await_args.kwargs
        assert "temperature" not in kwargs

    @pytest.mark.asyncio
    async def test_gpt41_passes_temperature(self):
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=_openai_resp("hello"))
        adapter = OpenAIAdapter(client_getter=lambda: client, api_key_getter=lambda: "sk")
        await adapter.complete(
            [{"role": "user", "content": "hi"}],
            "gpt-4.1",
            CompletionOptions(temperature=0.2),
        )
        kwargs = client.chat.completions.create.await_args.kwargs
        assert kwargs["temperature"] == 0.2

    @pytest.mark.asyncio
    async def test_generic_error_maps_to_unavailable_after_retries(self):
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
        adapter = OpenAIAdapter(client_getter=lambda: client, api_key_getter=lambda: "sk")
        with pytest.raises(ProviderUnavailableError):
            await adapter.complete([{"role": "user", "content": "hi"}], "gpt-5.5", CompletionOptions())
        assert client.chat.completions.create.call_count == 3  # retried

    @pytest.mark.asyncio
    async def test_bad_request_maps_to_invalid_no_retry(self):
        from openai import BadRequestError

        req = httpx.Request("POST", "http://x")
        resp = httpx.Response(400, request=req)
        err = BadRequestError("bad input", response=resp, body=None)
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(side_effect=err)
        adapter = OpenAIAdapter(client_getter=lambda: client, api_key_getter=lambda: "sk")
        with pytest.raises(ProviderInvalidResponseError):
            await adapter.complete([{"role": "user", "content": "hi"}], "gpt-5.5", CompletionOptions())
        assert client.chat.completions.create.call_count == 1  # no failover/retry on invalid

    @pytest.mark.asyncio
    async def test_unavailable_when_no_client(self):
        adapter = OpenAIAdapter(client_getter=lambda: None, api_key_getter=lambda: "")
        assert adapter.is_available() is False
        with pytest.raises(ProviderUnavailableError):
            await adapter.complete([{"role": "user", "content": "hi"}], "gpt-5.5", CompletionOptions())


class TestAnthropicAdapter:
    @pytest.mark.asyncio
    async def test_extracts_system_and_normalizes(self, monkeypatch):
        import anthropic

        fake_client = AsyncMock()
        fake_resp = SimpleNamespace(
            content=[SimpleNamespace(text="hi there")],
            usage=SimpleNamespace(input_tokens=7, output_tokens=3),
        )
        fake_client.messages.create = AsyncMock(return_value=fake_resp)
        monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda **kwargs: fake_client)

        adapter = AnthropicAdapter(api_key_getter=lambda: "k", voyage_key_getter=lambda: "")
        messages = [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "hello"},
        ]
        r = await adapter.complete(messages, "claude-sonnet-4-6", CompletionOptions())
        assert r.content == "hi there"
        assert (r.prompt_tokens, r.completion_tokens) == (7, 3)
        assert r.provider_used == "anthropic"
        _args, kwargs = fake_client.messages.create.call_args
        assert kwargs["system"] == "SYS"
        assert all(m["role"] != "system" for m in kwargs["messages"])

    def test_embed_requires_voyage_key(self):
        adapter = AnthropicAdapter(api_key_getter=lambda: "k", voyage_key_getter=lambda: "")
        with pytest.raises(ProviderUnavailableError):
            adapter.embed("hello")

    @pytest.mark.asyncio
    async def test_retries_transient_failure(self, monkeypatch):
        import anthropic

        import app.services.providers.base as base

        monkeypatch.setattr(base.asyncio, "sleep", AsyncMock())  # no real backoff delay
        fake_client = AsyncMock()
        fake_client.messages.create = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda **kwargs: fake_client)
        adapter = AnthropicAdapter(api_key_getter=lambda: "k", voyage_key_getter=lambda: "")
        with pytest.raises(ProviderUnavailableError):
            await adapter.complete([{"role": "user", "content": "hi"}], "claude-sonnet-4-6", CompletionOptions())
        assert fake_client.messages.create.call_count == 3  # retried with backoff


class TestGeminiAdapter:
    def test_role_mapping_and_system_prepend(self):
        adapter = GeminiAdapter(api_key_getter=lambda: "k")
        contents = adapter._to_contents(  # noqa: SLF001
            [
                {"role": "system", "content": "SYS"},
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
            ]
        )
        assert contents[0]["role"] == "user"
        assert contents[0]["parts"][0].startswith("SYS")
        assert contents[1]["role"] == "model"

    def test_unavailable_without_sdk(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.providers.gemini_adapter._try_import",
            lambda _name: None,
        )
        adapter = GeminiAdapter(api_key_getter=lambda: "k")
        assert adapter.is_available() is False


class TestEmbeddingFailover:
    def test_openai_primary(self, monkeypatch, mock_settings):
        monkeypatch.setattr(OpenAIAdapter, "embed", lambda self, text, model="m": [0.5, 0.5])
        vec, method = embed_with_failover("query", mock_settings)
        assert method == "openai"
        assert vec == [0.5, 0.5]

    def test_voyage_fallback(self, monkeypatch, mock_settings):
        monkeypatch.setattr(
            OpenAIAdapter, "embed", MagicMock(side_effect=ProviderUnavailableError("openai", "down"))
        )
        monkeypatch.setattr(AnthropicAdapter, "embed", lambda self, text, model="voyage-3": [0.9])
        # Voyage is only used when the corpus is Voyage-dimensioned (1024).
        settings = mock_settings.model_copy(
            update={"voyage_api_key": "vk", "openai_embedding_dimension": 1024, "voyage_embedding_enabled": True}
        )
        vec, method = embed_with_failover("query", settings)
        assert method == "voyage"
        assert vec == [0.9]

    def test_voyage_skipped_on_dimension_mismatch(self, monkeypatch, mock_settings):
        from app.rag.embedding import EmbeddingDimensionMismatchError

        monkeypatch.setattr(
            OpenAIAdapter, "embed", MagicMock(side_effect=ProviderUnavailableError("openai", "down"))
        )
        monkeypatch.setattr(AnthropicAdapter, "embed", lambda self, text, model="voyage-3": [0.9])
        settings = mock_settings.model_copy(
            update={
                "voyage_api_key": "vk",
                "openai_embedding_dimension": 1536,
                "voyage_embedding_enabled": True,
            }
        )
        with pytest.raises(EmbeddingDimensionMismatchError):
            embed_with_failover("query", settings)

    def test_voyage_disabled_by_config_gate(self, monkeypatch, mock_settings):
        monkeypatch.setattr(
            OpenAIAdapter, "embed", MagicMock(side_effect=ProviderUnavailableError("openai", "down"))
        )
        settings = mock_settings.model_copy(update={"voyage_api_key": "vk", "voyage_embedding_enabled": False})
        with pytest.raises(ValueError, match="voyage: disabled"):
            embed_with_failover("query", settings)

    def test_all_fail_raises(self, mock_settings):
        settings = mock_settings.model_copy(update={"openai_api_key": "", "voyage_api_key": ""})
        with pytest.raises(ValueError):
            embed_with_failover("query", settings)
