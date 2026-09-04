"""End-to-end: a real unified turn must attach tools that pass the guard.

This is the test whose absence let `unnarrowed_tool_attach_blocked` fire 109
times on 2026-08-13 before anyone noticed.

The guard was tested. The conversion helpers were tested. What was never tested
was the actual turn: that `run_unified_turn_shadow` reaches the model with tools
still carrying proof of narrowing. Mutation testing on 2026-09-02 confirmed the
gap was real -- removing the preserving branch (the exact pre-`65161f90` defect)
left every other test green.

So this test drives the real function and inspects what reaches the provider.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.narrowed_tools import assert_tools_narrowed
from app.services.unified_turn_reasoning_service import (
    _StreamedCompletion,
    run_unified_turn_shadow,
)


def _catalog(n: int = 60) -> list[dict[str, Any]]:
    """Big enough to clear the embed-min-catalog threshold."""
    tools = []
    for i in range(n):
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": f"hubspot_action_{i}",
                    "description": f"Search or update deals, contacts and companies ({i}).",
                    "parameters": {"type": "object", "properties": {}},
                },
                "integration": "hubspot",
                "invoke_action": "search",
            }
        )
    return tools


class _Settings(SimpleNamespace):
    """Real attributes only, so getattr(..., default) still works downstream."""

    def __init__(self) -> None:
        super().__init__(
            unified_turn_shadow_enabled=True,
            unified_turn_live_enabled=False,
            unified_turn_embedding_tool_retrieval=False,  # keyword path, no network
            unified_turn_progressive_schemas=True,
        )


def _completion(content: str = "Here are your deals.") -> Any:
    return _StreamedCompletion(
        content=content,
        tool_calls=[],
        first_token_ms=40,
        model_ttft_ms=35,
        latency_ms=120,
        model_total_ms=110,
        streamed=False,
    )


def _drive(message: str) -> tuple[Any, dict[str, Any]]:
    """Run a turn; capture the kwargs that reached the provider dispatch."""
    seen: dict[str, Any] = {}

    async def _capture(router: Any, openai_client: Any, **kw: Any) -> Any:
        seen.update(kw.get("kwargs") or {})
        return _completion()

    registry = MagicMock()
    registry.get_tools_for_agent.return_value = _catalog()

    # Pinned explicitly: the turn bails with openai_client_unavailable if the
    # shared router singleton has no client, which depends on whatever ran
    # earlier in the session. Without this the test passes alone and fails in
    # the full suite.
    router = MagicMock()
    router._openai = MagicMock()

    with patch(
        "app.services.unified_turn_reasoning_service.get_model_router",
        return_value=router,
    ), patch(
        "app.services.unified_turn_reasoning_service.get_tool_registry",
        return_value=registry,
    ), patch(
        "app.services.providers.provider_tool_router.provider_tools_configured",
        return_value=True,
    ), patch(
        "app.services.unified_turn_reasoning_service._complete_unified_turn",
        new=AsyncMock(side_effect=_capture),
    ):
        result = asyncio.run(
            run_unified_turn_shadow(
                org_id="00000000-0000-4000-8000-000000000001",
                user_id="00000000-0000-4000-8000-000000000002",
                conversation_id=None,
                message=message,
                task_state=None,
                conversation_history=None,
                connected_integrations=["hubspot"],
                settings=_Settings(),
            )
        )
    return result, seen


def test_a_real_task_turn_attaches_tools_that_pass_the_guard() -> None:
    result, seen = _drive("search my hubspot deals for acme")

    assert "unnarrowed_tool_attach_blocked" not in str(getattr(result, "error", "") or "")
    assert seen.get("tools"), "the turn attached no tools; the test proves nothing"
    assert_tools_narrowed(seen["tools"], where="test")  # must not raise


def test_the_attached_payload_still_carries_the_proof() -> None:
    _, seen = _drive("search my hubspot deals for acme")

    assert getattr(seen["tools"], "gravitre_narrowed", False) is True


def test_the_turn_does_not_fall_through_to_an_error_outcome() -> None:
    """The guard fails closed, so a regression shows up as outcome_kind=error."""
    result, _ = _drive("search my hubspot deals for acme")

    assert getattr(result, "outcome_kind", None) != "error", getattr(result, "error", None)


def test_attached_tools_are_sanitised_for_the_provider() -> None:
    _, seen = _drive("search my hubspot deals for acme")

    for tool in seen["tools"]:
        assert set(tool.keys()) == {"type", "function"}


def test_tool_choice_accompanies_tools() -> None:
    """Regression companion: tool_choice without tools is a hard 400."""
    _, seen = _drive("search my hubspot deals for acme")

    assert ("tool_choice" in seen) == bool(seen.get("tools"))


def _tool_call(name: str, args: dict[str, Any], call_id: str = "call_0") -> Any:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=__import__("json").dumps(args)),
    )


def test_model_skipping_search_catalog_tools_is_recovered_silently_not_told_to_repeat() -> None:
    """The 2026-09-04 leak: a model that calls a real connector tool before
    search_catalog_tools used to get told, in raw internal language,
    'Ask me again and I'll load parameters via search_catalog_tools first.'
    That forced the user to repeat themselves and leaked implementation
    details into text AND spoken voice output (same shared path).

    The fix auto-loads the schema server-side and gives the model one more
    silent retry. This test proves: (1) the user-visible outcome is not the
    old clarifying-question bounce, and (2) if a retry has to happen, no
    internal identifier ever reaches ``result.user_message``.
    """
    registry = MagicMock()
    registry.get_tools_for_agent.return_value = _catalog()
    registry._specs = {}

    router = MagicMock()
    router._openai = MagicMock()

    settings = _Settings()
    settings.unified_turn_progressive_preload_top = 0  # force the skip-ahead case

    calls: list[Any] = []

    async def _capture(router: Any, openai_client: Any, **kw: Any) -> Any:
        calls.append(kw)
        if len(calls) == 1:
            # Model calls the real tool directly — skips search_catalog_tools.
            return _StreamedCompletion(
                content="",
                tool_calls=[_tool_call("hubspot_action_0", {"query": "acme"})],
                first_token_ms=40,
                model_ttft_ms=35,
                latency_ms=120,
                model_total_ms=110,
                streamed=False,
            )
        # Auto-schema retry round: model now has the full schema attached
        # and calls the same tool again with real arguments.
        return _StreamedCompletion(
            content="",
            tool_calls=[_tool_call("hubspot_action_0", {"query": "acme"}, call_id="call_1")],
            first_token_ms=10,
            model_ttft_ms=8,
            latency_ms=60,
            model_total_ms=55,
            streamed=False,
        )

    with patch(
        "app.services.unified_turn_reasoning_service.get_model_router",
        return_value=router,
    ), patch(
        "app.services.unified_turn_reasoning_service.get_tool_registry",
        return_value=registry,
    ), patch(
        "app.services.providers.provider_tool_router.provider_tools_configured",
        return_value=True,
    ), patch(
        "app.services.unified_turn_reasoning_service._complete_unified_turn",
        new=AsyncMock(side_effect=_capture),
    ):
        result = asyncio.run(
            run_unified_turn_shadow(
                org_id="00000000-0000-4000-8000-000000000001",
                user_id="00000000-0000-4000-8000-000000000002",
                conversation_id=None,
                message="search my hubspot deals for acme",
                task_state=None,
                conversation_history=None,
                connected_integrations=["hubspot"],
                settings=settings,
            )
        )

    assert len(calls) == 2, "expected exactly one silent auto-retry round, not the old bounce"
    breakdown = getattr(result, "latency_breakdown", None) or {}
    assert breakdown.get("progressive_gate_auto_retry") is True

    message = str(getattr(result, "user_message", "") or "")
    for leaked in (
        "progressive disclosure",
        "search_catalog_tools",
        "full_schema_not_loaded",
        "hubspot_action_0",
        "catalog schemas",
        "Ask me again",
    ):
        assert leaked not in message, f"internal detail leaked into user_message: {leaked!r}"
