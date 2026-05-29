from __future__ import annotations

import pytest

from app.services.providers.base import (
    AllProvidersFailedError,
    CircuitBreaker,
    CompletionOptions,
    Message,
    ProviderAdapter,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderResponse,
    ProviderUnavailableError,
)
from app.services.providers.failover import build_priority, run_failover

MSGS: list[Message] = [{"role": "user", "content": "hi"}]
OPTS = CompletionOptions()


class StubAdapter(ProviderAdapter):
    def __init__(self, name: str, *, available: bool = True, error: Exception | None = None):
        self.provider_name = name
        self._available = available
        self._error = error
        self.calls = 0

    def is_available(self) -> bool:
        return self._available

    async def complete(self, messages, model, options) -> ProviderResponse:
        self.calls += 1
        if self._error:
            raise self._error
        return ProviderResponse(
            content="ok",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            model_used=model,
            provider_used=self.provider_name,
            latency_ms=1.0,
        )

    def embed(self, text: str, model: str) -> list[float]:
        return [0.0]


class TestBuildPriority:
    def test_auto_high_prefers_anthropic(self):
        assert build_priority("auto", "high") == [
            ("anthropic", "claude-sonnet-4-6"),
            ("openai", "gpt-4o"),
            ("gemini", "gemini-2.5-pro"),
        ]

    def test_auto_low_prefers_openai(self):
        assert build_priority("auto", "low")[0] == ("openai", "gpt-4o-mini")

    def test_preferred_anthropic_first(self):
        priority = build_priority("anthropic", "medium")
        assert priority[0] == ("anthropic", "claude-sonnet-4-6")
        assert [p for p, _ in priority] == ["anthropic", "openai", "gemini"]

    def test_preferred_gemini_first(self):
        assert [p for p, _ in build_priority("gemini", "low")] == ["gemini", "openai", "anthropic"]


class TestFailoverChain:
    @pytest.mark.asyncio
    async def test_primary_fails_secondary_succeeds(self):
        a = StubAdapter("openai", error=ProviderUnavailableError("openai", "down"))
        b = StubAdapter("anthropic")
        result = await run_failover(
            {"openai": a, "anthropic": b},
            [("openai", "m1"), ("anthropic", "m2")],
            MSGS,
            OPTS,
            CircuitBreaker(),
        )
        assert result.response.provider_used == "anthropic"
        assert a.calls == 1 and b.calls == 1

    @pytest.mark.asyncio
    async def test_two_fail_third_succeeds(self):
        a = StubAdapter("openai", error=ProviderRateLimitedError("openai", "429"))
        b = StubAdapter("anthropic", error=ProviderUnavailableError("anthropic", "down"))
        c = StubAdapter("gemini")
        result = await run_failover(
            {"openai": a, "anthropic": b, "gemini": c},
            [("openai", "m1"), ("anthropic", "m2"), ("gemini", "m3")],
            MSGS,
            OPTS,
            CircuitBreaker(),
        )
        assert result.response.provider_used == "gemini"
        assert (a.calls, b.calls, c.calls) == (1, 1, 1)

    @pytest.mark.asyncio
    async def test_all_fail_raises(self):
        a = StubAdapter("openai", error=ProviderUnavailableError("openai", "down"))
        b = StubAdapter("anthropic", error=ProviderUnavailableError("anthropic", "down"))
        with pytest.raises(AllProvidersFailedError):
            await run_failover(
                {"openai": a, "anthropic": b},
                [("openai", "m1"), ("anthropic", "m2")],
                MSGS,
                OPTS,
                CircuitBreaker(),
            )

    @pytest.mark.asyncio
    async def test_invalid_response_no_failover(self):
        a = StubAdapter("openai", error=ProviderInvalidResponseError("openai", "bad prompt"))
        b = StubAdapter("anthropic")
        with pytest.raises(ProviderInvalidResponseError):
            await run_failover(
                {"openai": a, "anthropic": b},
                [("openai", "m1"), ("anthropic", "m2")],
                MSGS,
                OPTS,
                CircuitBreaker(),
            )
        assert b.calls == 0  # secondary never attempted

    @pytest.mark.asyncio
    async def test_unavailable_adapter_skipped(self):
        a = StubAdapter("openai", available=False)
        b = StubAdapter("anthropic")
        result = await run_failover(
            {"openai": a, "anthropic": b},
            [("openai", "m1"), ("anthropic", "m2")],
            MSGS,
            OPTS,
            CircuitBreaker(),
        )
        assert result.response.provider_used == "anthropic"
        assert a.calls == 0


class TestCircuitBreaker:
    def test_trips_after_threshold_and_recovers_on_success(self):
        breaker = CircuitBreaker(failure_threshold=2, cooldown_s=60.0)
        assert breaker.is_open("openai") is False
        breaker.record_failure("openai")
        assert breaker.is_open("openai") is False
        breaker.record_failure("openai")
        assert breaker.is_open("openai") is True
        breaker.record_success("openai")
        assert breaker.is_open("openai") is False

    @pytest.mark.asyncio
    async def test_open_breaker_skips_provider_in_chain(self):
        breaker = CircuitBreaker(failure_threshold=1, cooldown_s=60.0)
        breaker.record_failure("openai")  # trip immediately
        assert breaker.is_open("openai") is True
        a = StubAdapter("openai")  # would succeed, but should be skipped
        b = StubAdapter("anthropic")
        result = await run_failover(
            {"openai": a, "anthropic": b},
            [("openai", "m1"), ("anthropic", "m2")],
            MSGS,
            OPTS,
            breaker,
        )
        assert result.response.provider_used == "anthropic"
        assert a.calls == 0  # skipped due to open breaker
