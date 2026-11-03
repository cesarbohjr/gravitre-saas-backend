"""No provider traffic: exercise the shared classical/unified recovery boundary."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.providers import provider_tool_router as tool_router
from app.services.providers.base import AllProvidersFailedError, CircuitBreaker


class HTTPFailure(Exception):
    def __init__(self, status):
        self.status_code = status
        super().__init__("sensitive SDK body")


@pytest.fixture
def router(monkeypatch):
    monkeypatch.setattr("app.services.tool_model_metering.authorize_tool_model_call", AsyncMock())
    return SimpleNamespace(settings=SimpleNamespace(
        openai_api_key="test", anthropic_api_key="test", ai_failover_enabled=True,
        preferred_ai_provider="openai"), _breaker=CircuitBreaker())


@pytest.mark.asyncio
async def test_classical_401_preserves_history_tools_and_returns_single_proposal(router, monkeypatch):
    messages = [{"role": "system", "content": "persona and task"},
                {"role": "user", "content": "Find another email provider"}]
    tools = object()
    response = SimpleNamespace(choices=["one authorized proposal"])
    once = AsyncMock(side_effect=[HTTPFailure(401), response])
    monkeypatch.setattr(tool_router, "_complete_with_tools_once", once)
    result = await tool_router.complete_with_tools(router, model="gpt-5.5", messages=messages, tools=tools)
    assert result is response
    assert once.await_count == 2
    assert once.await_args_list[1].kwargs["model"].startswith("claude")
    for call in once.await_args_list:
        assert call.kwargs["messages"] is messages
        assert call.kwargs["tools"] is tools


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 422])
async def test_invalid_input_does_not_failover(router, status):
    attempt = AsyncMock(side_effect=HTTPFailure(status))
    with pytest.raises(HTTPFailure):
        await tool_router.run_tool_failover(router, model="gpt-5.5", complete=attempt)
    assert attempt.await_count == 1


@pytest.mark.asyncio
async def test_disabled_failover_and_sanitized_exhaustion(router):
    router.settings.ai_failover_enabled = False
    attempt = AsyncMock(side_effect=HTTPFailure(401))
    with pytest.raises(AllProvidersFailedError) as error:
        await tool_router.run_tool_failover(router, model="gpt-5.5", complete=attempt)
    assert attempt.await_count == 1
    assert "sensitive" not in str(error.value)


@pytest.mark.asyncio
async def test_policy_denial_cannot_trigger_provider_switch(router, monkeypatch):
    authorize = AsyncMock(side_effect=PermissionError("denied"))
    monkeypatch.setattr("app.services.tool_model_metering.authorize_tool_model_call", authorize)
    attempt = AsyncMock()
    with pytest.raises(PermissionError):
        await tool_router.run_tool_failover(router, model="gpt-5.5", complete=attempt)
    attempt.assert_not_awaited()


@pytest.mark.asyncio
async def test_unified_401_recovers_without_classical_fallthrough(router, monkeypatch):
    from app.services import unified_turn_reasoning_service as unified
    result = SimpleNamespace(model_used="")
    once = AsyncMock(side_effect=[HTTPFailure(401), result])
    monkeypatch.setattr(unified, "_complete_unified_turn_once", once)
    messages = [{"role": "user", "content": "Use the other provider for that same task"}]
    kwargs = {"messages": messages, "tools": object(), "model": "gpt-5.5"}
    assert await unified._complete_unified_turn(router, None, model="gpt-5.5", kwargs=kwargs) is result
    assert result.model_used.startswith("claude")
    assert once.await_args_list[1].kwargs["kwargs"]["messages"] is messages


@pytest.mark.asyncio
@pytest.mark.parametrize("delta", ["text", "tool"])
async def test_partial_voice_or_tool_stream_never_replayed(router, monkeypatch, delta):
    from app.services import unified_turn_reasoning_service as unified
    async def partial(*args, **kwargs):
        if delta == "text":
            await kwargs["on_text_delta"]("Already spoken")
        else:
            kwargs["on_tool_call_delta"]()
        raise HTTPFailure(503)
    once = AsyncMock(side_effect=partial)
    monkeypatch.setattr(unified, "_complete_unified_turn_once", once)
    with pytest.raises(RuntimeError, match="partial_stream"):
        await unified._complete_unified_turn(router, None, model="gpt-5.5", kwargs={})
    assert once.await_count == 1


@pytest.mark.asyncio
async def test_real_unified_dispatch_401_to_anthropic(router, monkeypatch):
    import time
    from app.services import unified_turn_reasoning_service as unified
    from app.services.providers.tool_completion import ToolCompletionResult

    create = AsyncMock(side_effect=HTTPFailure(401))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    alternate = AsyncMock(return_value=ToolCompletionResult(content="Alternative found", tool_calls=[]))
    monkeypatch.setattr(tool_router, "_complete_anthropic_with_tools", alternate)
    messages = [{"role": "system", "content": "Keep task and persona"},
                {"role": "user", "content": "Find an Outlook alternative"}]
    started = time.perf_counter()
    result = await unified._complete_unified_turn(
        router, client, model="gpt-5.5", kwargs={"messages": messages},
        wall_start=started, model_start=started,
    )
    assert result.content == "Alternative found"
    assert result.model_used.startswith("claude")
    create.assert_awaited_once()
    alternate.assert_awaited_once()
    assert alternate.await_args.kwargs["messages"] == messages
