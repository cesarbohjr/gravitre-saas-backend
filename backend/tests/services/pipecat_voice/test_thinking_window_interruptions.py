"""Speech while the brain is thinking must not lose the request.

Pipecat cancels the in-flight LLM turn on any user turn start ("it's
thinking, speaking or running a function call, and the interruption below
cancels that"). Before this fix the backchannel strategy only held the
interruption while audio played, so a cough, "hmm" or "you there?" during the
seconds before the first token cancelled the request; the filler then never
became a turn, and "you there?" was answered as small talk.
"""
from __future__ import annotations

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    ProposedUserStartedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services.pipecat_voice.backchannel_turn_strategy import (
    BackchannelAwareUserTurnStartStrategy,
    is_hold_while_thinking,
)
from app.services.pipecat_voice.cognitive_llm import merge_unanswered_turn
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession


def _transcription(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="u1", timestamp="2026-10-09T00:00:00Z")


class _Recorder:
    def __init__(self) -> None:
        self.turn_started_calls = []
        self.reset_aggregation_calls = 0

    async def on_user_turn_started(self, _strategy, params) -> None:
        self.turn_started_calls.append(params)

    async def on_reset_aggregation(self, _strategy) -> None:
        self.reset_aggregation_calls += 1

    async def _noop(self, *_args, **_kwargs) -> None:
        return None


async def _make(*, generating: bool, grace_period_s: float = 0.9):
    session = VoicePipelineSession()
    session.assistant_generating = generating
    strategy = BackchannelAwareUserTurnStartStrategy(
        enable_interruptions=True, grace_period_s=grace_period_s, voice_session=session
    )
    await BaseObject.setup(strategy, TaskManager())
    recorder = _Recorder()
    strategy.add_event_handler("on_user_turn_started", recorder.on_user_turn_started)
    strategy.add_event_handler("on_reset_aggregation", recorder.on_reset_aggregation)
    strategy.add_event_handler("on_push_frame", recorder._noop)
    strategy.add_event_handler("on_broadcast_frame", recorder._noop)
    return strategy, recorder, session


@pytest.mark.parametrize(
    "text", ["you there?", "hello?", "are you still there", "hmm", "uh", "okay", "thanks", "take your time"]
)
def test_presence_checks_and_filler_are_held_while_thinking(text: str) -> None:
    assert is_hold_while_thinking(text)


@pytest.mark.parametrize(
    "text",
    ["stop", "never mind", "actually make it Thursday", "and cc Mike", "no, send it to Dana instead"],
)
def test_real_content_while_thinking_still_interrupts(text: str) -> None:
    assert not is_hold_while_thinking(text)


@pytest.mark.asyncio
async def test_you_there_while_thinking_does_not_cancel_the_request() -> None:
    strategy, recorder, _ = await _make(generating=True)
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    assert recorder.turn_started_calls == [], "held, not resolved instantly"
    await strategy.process_frame(_transcription("you there?"))
    assert len(recorder.turn_started_calls) == 1
    assert recorder.turn_started_calls[0].enable_interruptions is False
    assert recorder.reset_aggregation_calls == 1, "presence check must not become its own turn"
    # A late final of the same utterance is dropped again.
    await strategy.process_frame(_transcription("hello?"))
    assert recorder.reset_aggregation_calls == 2
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_correction_while_thinking_interrupts() -> None:
    strategy, recorder, _ = await _make(generating=True)
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    await strategy.process_frame(_transcription("actually make it Thursday"))
    assert len(recorder.turn_started_calls) == 1
    assert recorder.turn_started_calls[0].enable_interruptions is True
    assert recorder.reset_aggregation_calls == 0
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_silent_noise_timeout_while_thinking_does_not_interrupt() -> None:
    strategy, recorder, _ = await _make(generating=True, grace_period_s=0.05)
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    import asyncio

    await asyncio.sleep(0.15)
    assert len(recorder.turn_started_calls) == 1
    assert recorder.turn_started_calls[0].enable_interruptions is False
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_idle_bot_is_still_a_pass_through() -> None:
    strategy, recorder, _ = await _make(generating=False)
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    assert len(recorder.turn_started_calls) == 1
    assert recorder.turn_started_calls[0].enable_interruptions is True
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_speaking_path_is_unchanged() -> None:
    strategy, recorder, _ = await _make(generating=True)
    await strategy.process_frame(BotStartedSpeakingFrame())
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    await strategy.process_frame(_transcription("what about the other one?"))
    assert recorder.turn_started_calls[0].enable_interruptions is True
    await strategy.process_frame(BotStoppedSpeakingFrame())
    await strategy.cleanup()


# --- merge of a request cancelled before any answer -------------------------------

HISTORY = [
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": "Hey! What can I do for you?"},
    {"role": "user", "content": "Email Sarah the deck from yesterday"},
]


def test_cancelled_request_is_folded_into_the_next_turn() -> None:
    text, history = merge_unanswered_turn("Email Sarah the deck from yesterday", "and cc Mike", HISTORY)
    assert text == "Email Sarah the deck from yesterday, and cc Mike"
    assert history == HISTORY[:2]


def test_backing_off_withdraws_the_cancelled_request() -> None:
    text, history = merge_unanswered_turn("Email Sarah the deck from yesterday", "never mind", HISTORY)
    assert text == "never mind"
    assert history == HISTORY


def test_a_repeat_is_not_doubled() -> None:
    text, history = merge_unanswered_turn(
        "Email Sarah the deck from yesterday", "Email Sarah the deck from yesterday please", HISTORY
    )
    assert text == "Email Sarah the deck from yesterday please"
    assert history == HISTORY[:2]


def test_reporter_tracks_the_thinking_window() -> None:
    import asyncio

    from pipecat.frames.frames import LLMFullResponseEndFrame, LLMFullResponseStartFrame
    from pipecat.processors.frame_processor import FrameDirection

    from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter

    session = VoicePipelineSession()
    reporter = ElevenLabsInterruptReporter(voice_session=session)

    async def _run() -> None:
        reporter.push_frame = _noop_push  # type: ignore[method-assign]
        await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        assert session.assistant_generating is True
        await reporter.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
        assert session.assistant_generating is False

    async def _noop_push(*_args, **_kwargs) -> None:
        return None

    from unittest.mock import patch

    with patch(
        "pipecat.processors.frame_processor.FrameProcessor.process_frame", new=_noop_push
    ):
        asyncio.run(_run())


def test_barge_in_before_any_answer_carries_the_request_to_the_next_turn() -> None:
    """process_frame keeps the cancelled request; the next turn answers both."""
    import asyncio
    from types import SimpleNamespace
    from typing import Any
    from unittest.mock import AsyncMock, patch

    from pipecat.frames.frames import LLMContextFrame
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.frame_processor import FrameDirection

    from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
    from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService

    queries: list[str] = []
    histories: list[Any] = []

    async def _slow_stream(**kwargs: Any):
        queries.append(kwargs["query"])
        histories.append(kwargs.get("conversation_history"))
        yield AssistantStreamEvent(sse_type="data-intelligence", payload={"data": {}})
        if len(queries) == 1:
            await asyncio.sleep(5)
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Sent, with Mike copied."})
        yield AssistantStreamComplete(full_content="", tool_results=[], react_result=None, model="test")

    fake = type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(_slow_stream)})()
    service = GravitreCognitiveLLMService(
        app_settings=SimpleNamespace(voice_slow_tool_notice_seconds=0, voice_deep_ack_seconds=0),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
    )
    service.push_frame = AsyncMock()
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()
    service.start_processing_metrics = AsyncMock()
    service.stop_processing_metrics = AsyncMock()
    service._push_llm_text = AsyncMock()  # type: ignore[method-assign]

    first = [{"role": "user", "content": "Email Sarah the deck from yesterday"}]
    second = [*first, {"role": "user", "content": "and cc Mike"}]

    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def _run() -> None:
        task = asyncio.create_task(
            service.process_frame(LLMContextFrame(context=LLMContext(messages=first)), FrameDirection.DOWNSTREAM)
        )
        await asyncio.sleep(0.2)
        task.cancel()  # what Pipecat's interruption does to the in-flight turn
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert service._carry_user_text == "Email Sarah the deck from yesterday"
        await service.process_frame(
            LLMContextFrame(context=LLMContext(messages=second)), FrameDirection.DOWNSTREAM
        )

    with patch("pipecat.services.llm_service.LLMService.process_frame", new=_noop), patch(
        "app.operators.agent_intelligence.get_agent_intelligence", return_value=fake
    ), patch("app.services.shared_turn_preparation.guard_spoken_turn", new=AsyncMock(return_value=None)), patch(
        "app.services.shared_turn_preparation.build_turn_system_prompt", return_value=""
    ), patch("app.services.pipecat_voice.cognitive_llm.is_stop_requested", return_value=False):
        asyncio.run(_run())

    assert queries == ["Email Sarah the deck from yesterday", "Email Sarah the deck from yesterday, and cc Mike"]
    assert all(m.get("content") != "Email Sarah the deck from yesterday" for m in (histories[1] or []))
    assert service._carry_user_text is None


def _echo_loop_service():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
    from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter

    service = GravitreCognitiveLLMService(
        app_settings=SimpleNamespace(voice_slow_tool_notice_seconds=0, voice_deep_ack_seconds=0),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
    )
    service.push_frame = AsyncMock()
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()
    service.start_processing_metrics = AsyncMock()
    service.stop_processing_metrics = AsyncMock()
    service._push_llm_text = AsyncMock()  # type: ignore[method-assign]
    session = VoicePipelineSession()
    reporter = ElevenLabsInterruptReporter(voice_session=session)
    reporter.push_frame = AsyncMock()  # type: ignore[method-assign]
    service._interrupt_reporter = reporter
    return service, session


def _run_turns(service, script) -> list[str]:
    """Run ``script`` against ``service`` with the brain faked; return the queries it got."""
    import asyncio
    from typing import Any
    from unittest.mock import AsyncMock, patch

    from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent

    queries: list[str] = []

    async def _slow_stream(**kwargs: Any):
        queries.append(kwargs["query"])
        yield AssistantStreamEvent(sse_type="data-intelligence", payload={"data": {}})
        if len(queries) == 1:
            # The first turn says "let me check" and is then cut off.
            await service._speak_narration("Let me check your website traffic for this week.")
            await asyncio.sleep(5)
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "You had 1,200 visitors."})
        yield AssistantStreamComplete(full_content="", tool_results=[], react_result=None, model="test")

    fake = type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(_slow_stream)})()

    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    with patch("pipecat.services.llm_service.LLMService.process_frame", new=_noop), patch(
        "app.operators.agent_intelligence.get_agent_intelligence", return_value=fake
    ), patch("app.services.shared_turn_preparation.guard_spoken_turn", new=AsyncMock(return_value=None)), patch(
        "app.services.shared_turn_preparation.build_turn_system_prompt", return_value=""
    ), patch("app.services.pipecat_voice.cognitive_llm.is_stop_requested", return_value=False):
        asyncio.run(script())
    return queries


def _context_frame(*texts: str):
    from pipecat.frames.frames import LLMContextFrame
    from pipecat.processors.aggregators.llm_context import LLMContext

    return LLMContextFrame(context=LLMContext(messages=[{"role": "user", "content": t} for t in texts]))


def test_request_is_not_repeated_once_gravitre_started_talking() -> None:
    """Live report: voice kept restarting the traffic answer from the beginning."""
    import asyncio

    from pipecat.processors.frame_processor import FrameDirection

    service, _session = _echo_loop_service()
    first = "what's my website traffic"

    async def _script() -> None:
        task = asyncio.create_task(service.process_frame(_context_frame(first), FrameDirection.DOWNSTREAM))
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # "Let me check..." was already spoken, so the request is not re-run.
        assert service._carry_user_text is None
        await service.process_frame(_context_frame(first, "show me last month"), FrameDirection.DOWNSTREAM)

    queries = _run_turns(service, _script)
    assert queries == [first, "show me last month"]


def test_the_bots_own_voice_is_not_answered_as_a_new_turn() -> None:
    import asyncio

    from pipecat.processors.frame_processor import FrameDirection

    service, _session = _echo_loop_service()
    first = "what's my website traffic"

    async def _script() -> None:
        task = asyncio.create_task(service.process_frame(_context_frame(first), FrameDirection.DOWNSTREAM))
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # The mic picked up the narration and Flux transcribed it.
        await service.process_frame(
            _context_frame(first, "let me check your website traffic for this week"),
            FrameDirection.DOWNSTREAM,
        )

    queries = _run_turns(service, _script)
    assert queries == [first]


def test_echo_needs_a_near_verbatim_replay() -> None:
    session = VoicePipelineSession()
    session.note_bot_speech("Want me to dig into where the visits came from, or which pages did best?")
    assert session.is_echo_of_bot("dig into where the visits came from")
    assert not session.is_echo_of_bot("where the visits came from", strict=True)
    assert not session.is_echo_of_bot("yes show me the pages")
