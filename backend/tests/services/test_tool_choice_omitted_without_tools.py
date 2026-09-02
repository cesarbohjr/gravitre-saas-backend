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
