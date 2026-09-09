"""Prefix-cache reuse must survive the trip from OpenAI usage to the ReAct loop.

A tool-using voice turn costs three sequential LLM round trips. Attributing the
cold first one requires knowing how many prompt tokens the provider actually
reused, and the normalized tool-completion shape used to drop usage entirely.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.providers.provider_tool_router import _openai_cached_tokens
from app.services.providers.tool_completion import (
    ToolCompletionResult,
    make_openai_compatible_response,
)


def _usage(cached: object, present: bool = True) -> SimpleNamespace:
    if not present:
        return SimpleNamespace(prompt_tokens=100, completion_tokens=10)
    return SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=10,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
    )


class TestOpenAICachedTokens:
    def test_reads_a_cache_hit(self) -> None:
        assert _openai_cached_tokens(_usage(3840)) == 3840

    def test_zero_reuse_is_zero_not_none(self) -> None:
        # A cold call really did reuse nothing; that must stay distinguishable
        # from the provider failing to report the field at all.
        assert _openai_cached_tokens(_usage(0)) == 0

    def test_missing_details_is_none(self) -> None:
        assert _openai_cached_tokens(_usage(None, present=False)) is None

    def test_missing_cached_field_is_none(self) -> None:
        assert _openai_cached_tokens(_usage(None)) is None

    def test_absent_usage_is_none(self) -> None:
        assert _openai_cached_tokens(None) is None

    def test_dict_shaped_details(self) -> None:
        usage = SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=10,
            prompt_tokens_details={"cached_tokens": 512},
        )
        assert _openai_cached_tokens(usage) == 512

    def test_non_numeric_is_none(self) -> None:
        assert _openai_cached_tokens(_usage("lots")) is None


class TestCompatibleResponseCarriesUsage:
    def test_usage_survives_normalization(self) -> None:
        resp = make_openai_compatible_response(
            ToolCompletionResult(
                content="hi",
                prompt_tokens=4100,
                completion_tokens=42,
                cached_tokens=3840,
            )
        )
        assert resp.usage.prompt_tokens == 4100
        assert resp.usage.completion_tokens == 42
        assert resp.usage.prompt_tokens_details.cached_tokens == 3840

    def test_unreported_cache_stays_none(self) -> None:
        resp = make_openai_compatible_response(
            ToolCompletionResult(content="hi", prompt_tokens=4100)
        )
        assert resp.usage.prompt_tokens_details.cached_tokens is None

    def test_message_shape_is_unchanged(self) -> None:
        # The ReAct loop reads choices[0].message; adding usage must not disturb it.
        resp = make_openai_compatible_response(ToolCompletionResult(content="hi"))
        assert resp.choices[0].message.content == "hi"
        assert resp.choices[0].message.tool_calls is None
