"""The non-OpenAI provider path must survive the narrowing guard.

This is the behavioural half of the `unnarrowed_tool_attach_blocked` root cause
(traced 2026-09-02). 8 of the 119 events were logged at
`provider_tool_router.complete_with_tools`, not at `unified_turn.round_0`, and
the 2026-08-13 repair (`65161f90`) did not touch that path.

Only non-OpenAI models reach it: `_complete_unified_turn` sends OpenAI models to
the streaming branch, which never calls `complete_with_tools`. Because the
deployment routes unified turns to OpenAI models, the defect stopped producing
events without ever being fixed -- the failure mode simply stopped being
exercised. Any Anthropic or Gemini turn carrying tools would have tripped the
guard and dropped the turn to the classical path.

These tests exercise the path directly so it cannot go quiet again by accident.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.narrowed_tools import assert_tools_narrowed, mark_narrowed
from app.services.unified_turn_reasoning_service import _complete_unified_turn

TOOL = {
    "type": "function",
    "function": {"name": "hubspot_search_deals", "parameters": {"type": "object"}},
    "invoke_action": "search",
}


def _fake_response() -> Any:
    message = MagicMock()
    message.content = "Found 3 deals."
    message.tool_calls = []
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _kwargs_as_the_unified_turn_builds_them() -> dict[str, Any]:
    """Mirror the real attach: narrowed tools, converted for the provider."""
    narrowed = mark_narrowed([TOOL], source="embedding_narrow_tools_for_turn")
    assert_tools_narrowed(narrowed, where="test-precondition")
    return {
        "model": "claude-sonnet-4",
        "messages": [{"role": "user", "content": "search my deals"}],
        "tools": narrowed.as_openai_tools(),
        "tool_choice": "auto",
    }


def _run_through_provider(kwargs: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    seen: dict[str, Any] = {}

    async def _capture(router: Any, **call_kwargs: Any) -> Any:
        seen.update(call_kwargs)
        # The real guard, at the real call site.
        assert_tools_narrowed(
            call_kwargs.get("tools"),
            where="provider_tool_router.complete_with_tools",
        )
        return _fake_response()

    with patch(
        "app.services.providers.provider_tool_router.resolve_provider_for_model",
        return_value="anthropic",
    ), patch(
        "app.services.providers.provider_tool_router.complete_with_tools",
        new=AsyncMock(side_effect=_capture),
    ):
        result = asyncio.run(
            _complete_unified_turn(
                MagicMock(),
                MagicMock(),
                model="claude-sonnet-4",
                kwargs=kwargs,
                wall_start=0.0,
                model_start=0.0,
                timeout_s=20.0,
            )
        )
    return result, seen


def test_anthropic_turn_with_tools_is_not_blocked_by_the_guard() -> None:
    result, seen = _run_through_provider(_kwargs_as_the_unified_turn_builds_them())

    assert result.content == "Found 3 deals."
    assert len(seen["tools"]) == 1


def test_the_tools_reaching_the_provider_still_carry_the_proof() -> None:
    _, seen = _run_through_provider(_kwargs_as_the_unified_turn_builds_them())

    assert getattr(seen["tools"], "gravitre_narrowed", False) is True


def test_provider_receives_sanitised_tool_defs() -> None:
    """Carrying the marker must not smuggle retrieval metadata to the vendor."""
    _, seen = _run_through_provider(_kwargs_as_the_unified_turn_builds_them())

    assert set(seen["tools"][0].keys()) == {"type", "function"}


def test_the_old_plain_list_payload_would_have_been_blocked() -> None:
    """Reproduces the original defect, so the fix is not a coincidence."""
    narrowed = mark_narrowed([TOOL], source="embedding_narrow_tools_for_turn")
    kwargs = {
        "model": "claude-sonnet-4",
        "messages": [{"role": "user", "content": "search my deals"}],
        # The pre-fix expression.
        "tools": [dict(t) for t in narrowed],
        "tool_choice": "auto",
    }

    with pytest.raises(RuntimeError, match="unnarrowed_tool_attach_blocked"):
        _run_through_provider(kwargs)


def test_conversational_turn_without_tools_reaches_the_provider() -> None:
    kwargs = {
        "model": "claude-sonnet-4",
        "messages": [{"role": "user", "content": "thanks!"}],
    }

    result, seen = _run_through_provider(kwargs)

    assert result.content == "Found 3 deals."
    assert seen["tools"] == []
