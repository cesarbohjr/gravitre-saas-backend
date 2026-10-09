"""Speculative run and confirmed turn compute the same tier and mode.

The speculative run (SpeculativePrefetchProcessor on Flux's probable EOT) and
the confirmed turn (GravitreCognitiveLLMService) each build history their own
way. Adoption is only honest when both produced the same tier/mode for the
same final text and history. Synthetic contexts; the brain is faked.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.frames.frames import (
    InterimTranscriptionFrame,
    ProposedUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.operators.stream_events import AssistantStreamEvent
from app.services import operator_task_intent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.speculative_generation import (
    SpeculativeGenerationCoordinator,
    start_speculative_run,
)
from app.services.pipecat_voice.speculative_prefetch import SpeculativePrefetchProcessor

DURABLE = [
    {"role": "user", "content": "morning!"},
    {"role": "assistant", "content": "Morning. What's on your mind?"},
]
SOCKET_PRIOR = [
    {"role": "user", "content": "pull my pipeline from HubSpot"},
    {"role": "assistant", "content": "You have 12 open deals worth about 340k."},
]


class _Ctx:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self._messages = messages

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self._messages)


def _recording_router(calls: list[tuple[str, list | None, Any, str]]):
    real = operator_task_intent.resolve_voice_turn_routing

    def _wrapped(message, *, history=None, task_state=None):
        tier, mode = real(message, history=history, task_state=task_state)
        calls.append((message, [dict(m) for m in (history or [])], tier, mode))
        return tier, mode

    return _wrapped


async def _speculate(text: str, coordinator: SpeculativeGenerationCoordinator, captured: dict) -> None:
    async def _durable():
        return list(DURABLE), None, "conv-1"

    proc = SpeculativePrefetchProcessor(
        app_settings=SimpleNamespace(),
        org_id="org-1",
        user_id="user-1",
        agent={"id": "agent-1"},
        conversation_id="conv-1",
        speculative_coordinator=coordinator,
        min_chars=3,
        llm_context=_Ctx(SOCKET_PRIOR),
        durable_context_provider=_durable,
    )
    await BaseObject.setup(proc, TaskManager())
    proc.push_frame = AsyncMock()
    proc._prefetch = AsyncMock()

    intelligence = MagicMock()

    async def _stream(**kwargs):
        captured.update(kwargs)
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Answer."})

    intelligence.execute_task_streaming = _stream
    await proc.process_frame(
        InterimTranscriptionFrame(text=text, user_id="u1", timestamp="", language=None),
        FrameDirection.DOWNSTREAM,
    )
    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=intelligence):
        await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)
        run = coordinator._run
        assert run is not None
        await run.task


def _confirmed_service(coordinator: SpeculativeGenerationCoordinator) -> GravitreCognitiveLLMService:
    service = GravitreCognitiveLLMService(
        app_settings=object(),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
        conversation_id="conv-1",
        speculative_coordinator=coordinator,
    )
    service._durable_history_loaded = True
    service._durable_history = list(DURABLE)
    service.push_frame = AsyncMock()
    service._push_llm_text = AsyncMock()
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected_tier", "expected_mode"),
    [
        ("what's our revenue this quarter", "deep", "agent"),
        ("haha that's hilarious", "light", "fast"),
        ("explain how vector databases work", "medium", "standard"),
    ],
)
async def test_speculative_and_confirmed_turn_compute_the_same_tier(text, expected_tier, expected_mode) -> None:
    calls: list[tuple[str, list | None, Any, str]] = []
    captured: dict[str, Any] = {}
    coordinator = SpeculativeGenerationCoordinator()
    with patch.object(operator_task_intent, "resolve_voice_turn_routing", _recording_router(calls)):
        await _speculate(text, coordinator, captured)
        service = _confirmed_service(coordinator)
        with patch("app.operators.agent_intelligence.get_agent_intelligence") as mock_get_intel:
            mock_get_intel.return_value.execute_task_streaming = MagicMock(
                side_effect=AssertionError("matching speculative run must be adopted")
            )
            await service._run_gravitre_turn(_Ctx([*SOCKET_PRIOR, {"role": "user", "content": text}]))

    assert len(calls) == 2, calls
    (spec_text, spec_hist, spec_tier, spec_mode), (conf_text, conf_hist, conf_tier, conf_mode) = calls
    assert spec_text == conf_text
    assert spec_hist == conf_hist == [*DURABLE, *SOCKET_PRIOR]
    assert spec_tier == conf_tier
    assert (conf_tier.tier, conf_mode) == (expected_tier, expected_mode)
    assert spec_mode == conf_mode == captured["mode"]


@pytest.mark.asyncio
async def test_continuation_never_starts_a_speculative_run() -> None:
    coordinator = SpeculativeGenerationCoordinator()
    proc = SpeculativePrefetchProcessor(
        app_settings=SimpleNamespace(),
        org_id="org-1",
        user_id="user-1",
        agent={"id": "agent-1"},
        conversation_id="conv-1",
        speculative_coordinator=coordinator,
        min_chars=3,
    )
    await BaseObject.setup(proc, TaskManager())
    proc.push_frame = AsyncMock()
    proc._prefetch = AsyncMock()
    for text in ("yes, do that", "go ahead", "ok send it", "the second one"):
        await proc.process_frame(
            InterimTranscriptionFrame(text=text, user_id="u1", timestamp="", language=None),
            FrameDirection.DOWNSTREAM,
        )
        with patch("app.operators.agent_intelligence.get_agent_intelligence") as mock_get_intel:
            await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)
        mock_get_intel.assert_not_called()
        assert coordinator.has_pending_run is False


async def _events():
    yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Hey!"})


@pytest.mark.asyncio
async def test_prefix_adoption_is_refused_across_tiers() -> None:
    coordinator = SpeculativeGenerationCoordinator()
    run = start_speculative_run(text="hey there", runner=_events, create_task=asyncio.ensure_future)
    run.tier = "light"
    coordinator.set_run(run)
    await run.task
    assert coordinator.adopt("hey there pull my pipeline", prefix_max_extra_words=4, tier="deep") is None


@pytest.mark.asyncio
async def test_prefix_adoption_within_the_same_tier_still_works() -> None:
    coordinator = SpeculativeGenerationCoordinator()
    run = start_speculative_run(text="hey there", runner=_events, create_task=asyncio.ensure_future)
    run.tier = "light"
    coordinator.set_run(run)
    await run.task
    assert coordinator.adopt("hey there friend", prefix_max_extra_words=4, tier="light") is run


@pytest.mark.asyncio
async def test_exact_match_adopts_without_tier() -> None:
    coordinator = SpeculativeGenerationCoordinator()
    run = start_speculative_run(text="hey there", runner=_events, create_task=asyncio.ensure_future)
    coordinator.set_run(run)
    await run.task
    assert coordinator.adopt("Hey there!", tier="light") is run
