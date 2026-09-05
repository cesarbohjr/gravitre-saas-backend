"""Voice-latency follow-up (2026-09-05): AnthropicAdapter must reuse one
AsyncAnthropic client across calls instead of constructing (and tearing down)
a fresh httpx-backed client on every single complete()/stream() call — the
same class of "warm/persistent connection" gap already fixed for the OpenAI
adapter via model_router.py's process-singleton AsyncOpenAI().

These tests fake the `anthropic` module entirely (no real network calls) so
they can assert on identity/call-count of the constructor itself.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.providers.anthropic_adapter import AnthropicAdapter
from app.services.providers.base import CompletionOptions, Message


def _fake_anthropic_module(construct_calls: list[tuple]) -> SimpleNamespace:
    """A minimal fake of the `anthropic` module: AsyncAnthropic(...) records
    every construction call and returns a mock client whose
    `messages.create` resolves to a plausible response object.
    """

    def _construct(**kwargs):
        construct_calls.append((kwargs.get("api_key"), kwargs.get("timeout")))
        client = MagicMock()
        resp = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )
        client.messages.create = AsyncMock(return_value=resp)
        return client

    return SimpleNamespace(AsyncAnthropic=_construct)


class TestClientIsConstructedOnceAndReusedAcrossCompleteCalls:
    @pytest.mark.asyncio
    async def test_three_complete_calls_construct_the_client_exactly_once(self) -> None:
        construct_calls: list[tuple] = []
        fake_module = _fake_anthropic_module(construct_calls)
        adapter = AnthropicAdapter(
            api_key_getter=lambda: "sk-ant-test",
            voyage_key_getter=lambda: "",
            timeout_s=30.0,
        )
        messages: list[Message] = [{"role": "user", "content": "hi"}]  # type: ignore[list-item]
        options = CompletionOptions(max_tokens=16, temperature=None)

        with patch(
            "app.services.providers.anthropic_adapter._try_import",
            return_value=fake_module,
        ):
            for _ in range(3):
                await adapter.complete(messages, "claude-sonnet-4-6", options)

        # MUTATION PROOF: reverting the fix (constructing AsyncAnthropic inline
        # inside _attempt() again) makes this 3, not 1.
        assert len(construct_calls) == 1, (
            f"expected exactly one AsyncAnthropic() construction across 3 calls, "
            f"got {len(construct_calls)}"
        )
        assert construct_calls[0] == ("sk-ant-test", 30.0)

    @pytest.mark.asyncio
    async def test_same_underlying_client_object_is_reused(self) -> None:
        adapter = AnthropicAdapter(
            api_key_getter=lambda: "sk-ant-test",
            voyage_key_getter=lambda: "",
            timeout_s=30.0,
        )
        construct_calls: list[tuple] = []
        fake_module = _fake_anthropic_module(construct_calls)

        with patch(
            "app.services.providers.anthropic_adapter._try_import",
            return_value=fake_module,
        ):
            options = CompletionOptions(max_tokens=16, temperature=None)
            messages: list[Message] = [{"role": "user", "content": "hi"}]  # type: ignore[list-item]
            await adapter.complete(messages, "claude-sonnet-4-6", options)
            first_client = adapter._client
            await adapter.complete(messages, "claude-sonnet-4-6", options)
            second_client = adapter._client

        assert first_client is second_client is not None

    @pytest.mark.asyncio
    async def test_api_key_change_invalidates_the_cached_client(self) -> None:
        """A rotated key must not silently keep using the old client."""
        construct_calls: list[tuple] = []
        fake_module = _fake_anthropic_module(construct_calls)
        current_key = {"value": "sk-ant-old"}
        adapter = AnthropicAdapter(
            api_key_getter=lambda: current_key["value"],
            voyage_key_getter=lambda: "",
            timeout_s=30.0,
        )
        options = CompletionOptions(max_tokens=16, temperature=None)
        messages: list[Message] = [{"role": "user", "content": "hi"}]  # type: ignore[list-item]

        with patch(
            "app.services.providers.anthropic_adapter._try_import",
            return_value=fake_module,
        ):
            await adapter.complete(messages, "claude-sonnet-4-6", options)
            current_key["value"] = "sk-ant-new"
            await adapter.complete(messages, "claude-sonnet-4-6", options)

        assert len(construct_calls) == 2
        assert construct_calls[0][0] == "sk-ant-old"
        assert construct_calls[1][0] == "sk-ant-new"


class TestStreamAlsoReusesTheCachedClient:
    @pytest.mark.asyncio
    async def test_stream_and_complete_share_the_same_cached_client(self) -> None:
        construct_calls: list[tuple] = []

        class _FakeStreamCtx:
            def __init__(self) -> None:
                self.text_stream = _aiter(["ok"])

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get_final_message(self):
                return SimpleNamespace(usage=SimpleNamespace(input_tokens=1, output_tokens=1))

        def _construct(**kwargs):
            construct_calls.append((kwargs.get("api_key"), kwargs.get("timeout")))
            client = MagicMock()
            resp = SimpleNamespace(
                content=[SimpleNamespace(type="text", text="ok")],
                usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            )
            client.messages.create = AsyncMock(return_value=resp)
            client.messages.stream = MagicMock(return_value=_FakeStreamCtx())
            return client

        fake_module = SimpleNamespace(AsyncAnthropic=_construct)
        adapter = AnthropicAdapter(
            api_key_getter=lambda: "sk-ant-test",
            voyage_key_getter=lambda: "",
            timeout_s=30.0,
        )
        options = CompletionOptions(max_tokens=16, temperature=None)
        messages: list[Message] = [{"role": "user", "content": "hi"}]  # type: ignore[list-item]

        with patch(
            "app.services.providers.anthropic_adapter._try_import",
            return_value=fake_module,
        ):
            await adapter.complete(messages, "claude-sonnet-4-6", options)
            async for _chunk in adapter.stream(messages, "claude-sonnet-4-6", options):
                pass

        assert len(construct_calls) == 1, "complete() and stream() must share one cached client"


async def _aiter(items):
    for item in items:
        yield item
