"""OpenAI rejects tool_choice when no tools are attached.

Found by tracing the `outcome_error` LIVE fallthrough branch. 15 of 142 events
over 30 days were:

    Error code: 400 - Invalid value for 'tool_choice': 'tool_choice' is only
    allowed when 'tools' are specified.

still firing as recently as 2026-09-01. `_complete_openai_with_tools`
unconditionally sent both `tools` and `tool_choice`, and both callers can
legitimately arrive with an empty tool list:

    unified_turn_reasoning_service.py:875  sets tool_choice="none" for
        conversational turns, and only adds `tools` when it has some
    react_engine.py:769                    passes `tools if tools else []`

Fixed at the provider adapter rather than at the two callers: that is the single
place the vendor contract is violated, so a third caller cannot reintroduce it.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.services.providers import provider_tool_router as ptr


class _Captor:
    """Minimal stand-in for the OpenAI client, recording the request kwargs."""

    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}
        self.chat = self
        self.completions = self

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs

        class _Msg:
            content = "ok"
            tool_calls: list[Any] = []

        class _Choice:
            message = _Msg()
            finish_reason = "stop"

        class _Resp:
            choices = [_Choice()]
            usage = None

        return _Resp()


TOOL = {
    "type": "function",
    "function": {"name": "hubspot_deals_list", "parameters": {"type": "object"}},
}


@pytest.mark.asyncio
async def test_no_tools_omits_both_keys() -> None:
    """The actual 400: neither key may be sent when there are no tools."""
    client = _Captor()

    await ptr._complete_openai_with_tools(
        openai_client=client,
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        tool_choice="none",
        temperature=None,
    )

    assert "tool_choice" not in client.kwargs, (
        "OpenAI rejects tool_choice without tools; this is the 400 that surfaced "
        "as an outcome_error fallthrough"
    )
    assert "tools" not in client.kwargs, "an empty tools list should not be sent"


@pytest.mark.asyncio
async def test_conversational_none_choice_is_the_real_regression_case() -> None:
    """tool_choice="none" with no tools is exactly what the LIVE path sends."""
    client = _Captor()

    await ptr._complete_openai_with_tools(
        openai_client=client,
        model="gpt-4.1",
        messages=[{"role": "user", "content": "thanks, that helped"}],
        tools=[],
        tool_choice="none",
        temperature=0.2,
    )

    assert "tool_choice" not in client.kwargs
    assert client.kwargs["model"] == "gpt-4.1"
    assert client.kwargs["temperature"] == 0.2


@pytest.mark.asyncio
async def test_tools_present_still_sends_both_keys() -> None:
    """The fix must not disable tool calling on the turns that do have tools."""
    client = _Captor()

    await ptr._complete_openai_with_tools(
        openai_client=client,
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": "list my deals"}],
        tools=[TOOL],
        tool_choice="auto",
        temperature=None,
    )

    assert client.kwargs["tools"] == [TOOL]
    assert client.kwargs["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_tools_present_defaults_choice_to_auto() -> None:
    client = _Captor()

    await ptr._complete_openai_with_tools(
        openai_client=client,
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": "list my deals"}],
        tools=[TOOL],
        tool_choice="",
        temperature=None,
    )

    assert client.kwargs["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_tools_present_honours_an_explicit_none() -> None:
    """With tools attached, "none" is a valid instruction and must survive."""
    client = _Captor()

    await ptr._complete_openai_with_tools(
        openai_client=client,
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": "just chat"}],
        tools=[TOOL],
        tool_choice="none",
        temperature=None,
    )

    assert client.kwargs["tool_choice"] == "none"
    assert client.kwargs["tools"] == [TOOL]


@pytest.mark.asyncio
async def test_temperature_is_omitted_when_none() -> None:
    client = _Captor()

    await ptr._complete_openai_with_tools(
        openai_client=client,
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        tool_choice="auto",
        temperature=None,
    )

    assert "temperature" not in client.kwargs


# --- the STREAMING path, which is where the production 400s actually came from ---
#
# Fixing the adapter above was one layer too low. resolve_provider_for_model
# routes OpenAI models straight to _complete_unified_turn_stream, which never
# touches provider_tool_router, so gpt-4o-mini kept 400ing at 56b4f1a1 after the
# adapter fix was already live. These tests cover the path that actually broke.


class _StreamCaptor:
    """Records the streaming request kwargs and yields an empty stream."""

    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}
        self.chat = self
        self.completions = self

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs

        async def _agen():
            if False:  # pragma: no cover - deliberately empty stream
                yield None

        return _agen()


@pytest.mark.asyncio
async def test_streaming_path_omits_tool_choice_without_tools() -> None:
    """The real regression: conversational LIVE turns stream with no tools."""
    from app.services import unified_turn_reasoning_service as uts

    client = _StreamCaptor()

    await uts._complete_unified_turn_stream(
        client,
        kwargs={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "thanks, that helped"}],
            "tool_choice": "none",
        },
        wall_start=0.0,
        model_start=0.0,
        timeout_s=20.0,
    )

    assert "tool_choice" not in client.kwargs, (
        "this is the exact 400 seen on gpt-4o-mini in production: tool_choice "
        "sent on a conversational turn that attaches no tools"
    )
    assert "tools" not in client.kwargs
    assert client.kwargs["stream"] is True


@pytest.mark.asyncio
async def test_streaming_path_keeps_tool_choice_with_tools() -> None:
    """Tool-shaped streaming turns must still be able to call tools."""
    from app.services import unified_turn_reasoning_service as uts

    client = _StreamCaptor()

    await uts._complete_unified_turn_stream(
        client,
        kwargs={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "list my deals"}],
            "tools": [TOOL],
            "tool_choice": "auto",
        },
        wall_start=0.0,
        model_start=0.0,
        timeout_s=20.0,
    )

    assert client.kwargs["tools"] == [TOOL]
    assert client.kwargs["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_streaming_path_drops_an_empty_tools_list() -> None:
    """An explicit empty list is the same contract violation as omitting it."""
    from app.services import unified_turn_reasoning_service as uts

    client = _StreamCaptor()

    await uts._complete_unified_turn_stream(
        client,
        kwargs={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hey"}],
            "tools": [],
            "tool_choice": "auto",
        },
        wall_start=0.0,
        model_start=0.0,
        timeout_s=20.0,
    )

    assert "tools" not in client.kwargs
    assert "tool_choice" not in client.kwargs
