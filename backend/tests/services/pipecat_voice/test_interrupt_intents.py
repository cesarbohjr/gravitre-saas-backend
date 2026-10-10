"""Interruption intents (voice_interrupt_intents_v1), each class with the flag off and on.

backchannel  -> keep speaking, nothing becomes a user turn
explain      -> speech stops, the explanation is answered, the paused request stays
correction   -> speech stops, the interrupted request is revised (merge_unanswered_turn)
speech stop  -> speech is silenced, the work is NOT cancelled, no write stop is armed
task cancel  -> pending writes stay refused, the report says what had already happened

Flag off is today's behaviour: every non-backchannel interruption stops the
reply and becomes an ordinary turn the brain answers.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    Frame,
    InterimTranscriptionFrame,
    InterruptionFrame,
    LLMContextFrame,
    LLMFullResponseStartFrame,
    OutputTransportMessageUrgentFrame,
    ProposedUserStartedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services import chat_turn_cancel_service, voice_barge_in_write
from app.services.pipecat_voice.backchannel_classifier import (
    BackchannelClassification,
    InterruptIntent,
    classify_interrupt_intent,
    classify_user_utterance,
    could_become_speech_stop,
)
from app.services.pipecat_voice.backchannel_turn_strategy import (
    BackchannelAwareUserTurnStartStrategy,
)
from app.services.pipecat_voice.cognitive_llm import (
    VOICE_EXPLAIN_INTERRUPTION_NOTE,
    GravitreCognitiveLLMService,
    describe_cancelled_work,
)
from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from app.services.tool_types import ToolValidationError

ORG = "00000000-0000-4000-8000-000000000001"
USER = "00000000-0000-4000-8000-000000000002"
CONV = "00000000-0000-4000-8000-000000000003"
WRITES = {"email.send", "crm.update"}

FLAG_STATES = pytest.mark.parametrize("intents_on", [False, True], ids=["flag_off", "flag_on"])


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch):
    chat_turn_cancel_service.reset_local_stops_for_tests()
    voice_barge_in_write.reset_write_effects_for_tests()
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    monkeypatch.setattr("app.services.pipecat_voice.voice_latency_metrics._write", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.services.voice_barge_in_write.action_is_mutating_write", lambda action: action in WRITES
    )
    yield
    chat_turn_cancel_service.reset_local_stops_for_tests()


# --- classifier ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("mm-hmm", InterruptIntent.BACKCHANNEL),
        ("right", InterruptIntent.BACKCHANNEL),
        ("ok", InterruptIntent.BACKCHANNEL),
        ("explain that number", InterruptIntent.EXPLAIN),
        ("wait what does that mean", InterruptIntent.EXPLAIN),
        ("where does that number come from?", InterruptIntent.EXPLAIN),
        ("use last quarter instead", InterruptIntent.CORRECTION),
        ("no, Acme not Northwind", InterruptIntent.CORRECTION),
        ("actually make it Search Console", InterruptIntent.CORRECTION),
        ("stop talking", InterruptIntent.SPEECH_STOP),
        ("be quiet", InterruptIntent.SPEECH_STOP),
        ("stop talking, keep working", InterruptIntent.SPEECH_STOP),
        ("cancel it", InterruptIntent.TASK_CANCEL),
        ("cancel that", InterruptIntent.TASK_CANCEL),
        ("don't send it", InterruptIntent.TASK_CANCEL),
        ("stop talking and cancel it", InterruptIntent.TASK_CANCEL),
        ("stop", InterruptIntent.STOP),
        ("hold on", InterruptIntent.STOP),
        ("no thanks", InterruptIntent.NEW_REQUEST),
        ("who owns the Acme account?", InterruptIntent.NEW_REQUEST),
        ("now show me the pipeline", InterruptIntent.NEW_REQUEST),
    ],
)
def test_interrupt_intent_classes(text: str, intent: InterruptIntent) -> None:
    assert classify_interrupt_intent(text) is intent


def test_legacy_classes_are_unchanged() -> None:
    assert classify_user_utterance("stop talking") is BackchannelClassification.STOP_COMMAND
    assert classify_user_utterance("cancel that") is BackchannelClassification.STOP_COMMAND
    assert classify_user_utterance("right") is BackchannelClassification.BACKCHANNEL
    assert classify_user_utterance("mm-hmm") is BackchannelClassification.INTERRUPTION


def test_only_the_start_of_a_speech_stop_waits_for_more_words() -> None:
    assert could_become_speech_stop("stop")
    assert could_become_speech_stop("okay stop")
    assert not could_become_speech_stop("stop talking")
    assert not could_become_speech_stop("cancel")
    assert not could_become_speech_stop("show me revenue")


# --- turn start strategy (overlapping speech while the bot talks) --------------


class _Recorder:
    def __init__(self) -> None:
        self.started: list[Any] = []
        self.resets = 0
        self.broadcasts: list[Any] = []

    async def on_user_turn_started(self, _s, params) -> None:
        self.started.append(params)

    async def on_reset_aggregation(self, _s) -> None:
        self.resets += 1

    async def on_push_frame(self, *_a, **_k) -> None:
        return None

    async def on_broadcast_frame(self, _s, frame_cls, **_k) -> None:
        self.broadcasts.append(frame_cls)


async def _strategy(intents_on: bool, session: VoicePipelineSession | None = None):
    session = session or VoicePipelineSession()
    strategy = BackchannelAwareUserTurnStartStrategy(
        enable_interruptions=True,
        grace_period_s=5.0,
        max_wordless_wait_s=0.0,
        gravitre_settings=SimpleNamespace(voice_interrupt_intents_v1=intents_on),
        voice_session=session,
    )
    await BaseObject.setup(strategy, TaskManager())
    rec = _Recorder()
    for name in ("on_user_turn_started", "on_reset_aggregation", "on_push_frame", "on_broadcast_frame"):
        strategy.add_event_handler(name, getattr(rec, name))
    await strategy.process_frame(BotStartedSpeakingFrame())
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    return strategy, rec, session


def _final(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="u1", timestamp="2026-10-10T00:00:00Z")


def _interim(text: str) -> InterimTranscriptionFrame:
    return InterimTranscriptionFrame(text=text, user_id="u1", timestamp="2026-10-10T00:00:00Z")


@pytest.mark.asyncio
@FLAG_STATES
async def test_backchannel_keeps_the_reply_going(intents_on: bool) -> None:
    strategy, rec, _ = await _strategy(intents_on)
    await strategy.process_frame(_final("right"))
    assert rec.started[-1].enable_interruptions is False
    assert rec.resets == 1, "a backchannel never becomes a user turn"
    await strategy.cleanup()


@pytest.mark.asyncio
@FLAG_STATES
async def test_mm_hmm_is_a_backchannel_only_with_the_flag(intents_on: bool) -> None:
    strategy, rec, _ = await _strategy(intents_on)
    await strategy.process_frame(_final("mm-hmm"))
    assert rec.started[-1].enable_interruptions is (not intents_on)
    assert rec.resets == (1 if intents_on else 0)
    await strategy.cleanup()


@pytest.mark.asyncio
@FLAG_STATES
@pytest.mark.parametrize(
    "text", ["wait what does that mean", "use last quarter instead", "no, Acme not Northwind", "cancel it"]
)
async def test_explain_correction_and_cancel_stop_the_speech(intents_on: bool, text: str) -> None:
    strategy, rec, _ = await _strategy(intents_on)
    await strategy.process_frame(_final(text))
    assert rec.started[-1].enable_interruptions is True
    assert rec.resets == 0, "the words are the next turn"
    await strategy.cleanup()


@pytest.mark.asyncio
@FLAG_STATES
async def test_speech_stop_silences_without_interrupting_the_work(intents_on: bool) -> None:
    session = VoicePipelineSession()
    silenced: list[bool] = []

    async def _handler() -> bool:
        silenced.append(True)
        return True

    session.speech_stop_handler = _handler
    strategy, rec, _ = await _strategy(intents_on, session)
    await strategy.process_frame(_final("stop talking, keep working"))
    if intents_on:
        assert silenced == [True]
        assert rec.started[-1].enable_interruptions is False, "the brain's turn must not be cancelled"
        assert rec.resets == 1, "'stop talking' is not a request to answer"
        # Later finals of the same utterance stay out of the context too.
        await strategy.process_frame(_final("please"))
        assert rec.resets == 2
        assert rec.broadcasts == []
    else:
        assert silenced == []
        assert rec.started[-1].enable_interruptions is True
    await strategy.cleanup()


@pytest.mark.asyncio
@FLAG_STATES
async def test_a_bare_stop_interim_waits_for_the_rest_only_with_the_flag(intents_on: bool) -> None:
    session = VoicePipelineSession()
    session.speech_stop_handler = AsyncMock(return_value=True)
    strategy, rec, _ = await _strategy(intents_on, session)
    await strategy.process_frame(_interim("stop"))
    if intents_on:
        assert rec.started == [], "'stop' may still become 'stop talking'"
        await strategy.process_frame(_interim("stop talking"))
        assert rec.started[-1].enable_interruptions is False
        session.speech_stop_handler.assert_awaited_once()
    else:
        assert rec.started[-1].enable_interruptions is True
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_speech_stop_that_turns_into_cancel_interrupts_after_all() -> None:
    session = VoicePipelineSession()
    session.speech_stop_handler = AsyncMock(return_value=True)
    strategy, rec, _ = await _strategy(True, session)
    await strategy.process_frame(_interim("stop talking"))
    assert rec.started[-1].enable_interruptions is False
    await strategy.process_frame(_final("stop talking and cancel it"))
    assert rec.broadcasts == [InterruptionFrame], "a cancel must reach the running work"
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_speech_stop_falls_back_to_an_interruption_when_nothing_was_silenced() -> None:
    session = VoicePipelineSession()
    session.speech_stop_handler = AsyncMock(return_value=False)
    strategy, rec, _ = await _strategy(True, session)
    await strategy.process_frame(_final("stop talking"))
    assert rec.started[-1].enable_interruptions is True
    await strategy.cleanup()


# --- interrupt reporter: silencing a reply ----------------------------------------


async def _reporter(session: VoicePipelineSession, *, conversation_id: str | None = CONV):
    reporter = ElevenLabsInterruptReporter(
        settings=SimpleNamespace(),
        org_id=ORG,
        user_id=USER,
        conversation_id=conversation_id,
        voice_session=session,
    )
    await BaseObject.setup(reporter, TaskManager())
    pushed: list[tuple[Frame, FrameDirection]] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        pushed.append((frame, direction))

    reporter.push_frame = _capture  # type: ignore[method-assign]
    return reporter, pushed


@pytest.mark.asyncio
async def test_silencing_a_reply_keeps_its_work_and_arms_no_write_stop() -> None:
    session = VoicePipelineSession()
    reporter, pushed = await _reporter(session)
    session.begin_reply()
    await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    pushed.clear()

    assert await reporter.silence_current_reply() is True
    assert session.reply_muted(1)
    assert session.reply_audio_suppressed(1)
    assert all(direction is FrameDirection.DOWNSTREAM for _, direction in pushed), "nothing may reach the brain"
    messages = [f.message for f, _ in pushed if isinstance(f, OutputTransportMessageUrgentFrame)]
    interrupted = [m for m in messages if m["type"] == "speech.interrupted"]
    assert interrupted and interrupted[0]["intent"] == "speech_stop" and interrupted[0]["work_continues"] is True
    assert interrupted[0]["reply_id"] == 1
    notices = [m for m in messages if m["type"] == "assistant_notice"]
    assert len(notices) == 1
    assert any(isinstance(f, InterruptionFrame) for f, _ in pushed), "TTS and transport are flushed"
    assert chat_turn_cancel_service.is_stop_requested(ORG, CONV) is False, "writes stay allowed"

    # Saying it again does not repeat the note.
    pushed.clear()
    await reporter.silence_current_reply()
    assert not [
        f for f, _ in pushed if isinstance(f, OutputTransportMessageUrgentFrame) and f.message["type"] == "assistant_notice"
    ]
    # The next reply speaks normally.
    session.begin_reply()
    assert not session.reply_audio_suppressed(2)
    await reporter.settle_barge_in()


@pytest.mark.asyncio
async def test_nothing_to_silence_when_idle() -> None:
    session = VoicePipelineSession()
    reporter, pushed = await _reporter(session)
    assert await reporter.silence_current_reply() is False
    assert pushed == []


# --- cognitive bridge: the turn after the barge-in ----------------------------------


class _Harness:
    def __init__(self, intents_on: bool, *, conversation_id: str | None = None) -> None:
        self.settings = SimpleNamespace(
            voice_slow_tool_notice_seconds=0,
            voice_deep_ack_seconds=0,
            voice_interrupt_intents_v1=intents_on,
        )
        self.service = GravitreCognitiveLLMService(
            app_settings=self.settings, org_id=ORG, user_id=USER, conversation_id=conversation_id
        )
        for name in (
            "push_frame",
            "start_ttfb_metrics",
            "stop_ttfb_metrics",
            "start_processing_metrics",
            "stop_processing_metrics",
            "_push_llm_text",
        ):
            setattr(self.service, name, AsyncMock())
        self.session = VoicePipelineSession()
        self.reporter = ElevenLabsInterruptReporter(
            settings=self.settings,
            org_id=ORG,
            user_id=USER,
            conversation_id=conversation_id,
            voice_session=self.session,
        )
        self.reporter.push_frame = AsyncMock()  # type: ignore[method-assign]
        self.service._interrupt_reporter = self.reporter
        self.calls: list[dict[str, Any]] = []
        self.first_turn_narration: str | None = None
        self.persisted: list[dict[str, Any]] = []
        self.during_first_turn: Any = None

    async def _stream(self, **kwargs: Any):
        from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent

        self.calls.append(kwargs)
        yield AssistantStreamEvent(sse_type="data-intelligence", payload={"data": {}})
        if len(self.calls) == 1:
            if self.first_turn_narration:
                await self.service._speak_narration(self.first_turn_narration)
            if self.during_first_turn is not None:
                self.during_first_turn()
            await asyncio.sleep(5)
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Here is the answer."})
        yield AssistantStreamComplete(full_content="", tool_results=[], react_result=None, model="test")

    async def barge_in_during(self, first: str) -> None:
        """Run turn 1, cut it off with a real barge-in, cancel the brain's task."""
        await BaseObject.setup(self.reporter, TaskManager())
        task = asyncio.create_task(self.service.process_frame(_ctx(first), FrameDirection.DOWNSTREAM))
        await asyncio.sleep(0.3)
        await self.reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await self.reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def turn(self, *texts: str) -> None:
        await self.service.process_frame(_ctx(*texts), FrameDirection.DOWNSTREAM)

    def run(self, script) -> None:
        fake = type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(self._stream)})()

        def _persist(_settings, **kwargs: Any):
            self.persisted.append(kwargs)
            return CONV, "assistant-row"

        async def _noop(*_a: Any, **_k: Any) -> None:
            return None

        with patch("pipecat.services.llm_service.LLMService.process_frame", new=_noop), patch(
            "app.operators.agent_intelligence.get_agent_intelligence", return_value=fake
        ), patch("app.services.shared_turn_preparation.guard_spoken_turn", new=AsyncMock(return_value=None)), patch(
            "app.services.shared_turn_preparation.build_turn_system_prompt", return_value=""
        ), patch("app.services.shared_turn_preparation.persist_completed_turn", new=_persist), patch.object(
            GravitreCognitiveLLMService, "_ensure_durable_context", new=AsyncMock()
        ), patch.object(
            GravitreCognitiveLLMService, "_prepare_conversation", new=AsyncMock()
        ), patch.object(
            GravitreCognitiveLLMService, "_refresh_durable_tail", new=AsyncMock()
        ):
            asyncio.run(script())

    def spoken_client_text(self) -> str:
        out = []
        for call in self.service.push_frame.await_args_list:
            frame = call.args[0]
            if isinstance(frame, OutputTransportMessageUrgentFrame) and frame.message.get("type") == "assistant_text":
                out.append(frame.message["delta"])
        return "".join(out)


def _ctx(*texts: str) -> LLMContextFrame:
    return LLMContextFrame(context=LLMContext(messages=[{"role": "user", "content": t} for t in texts]))


@FLAG_STATES
def test_explain_keeps_the_paused_request(intents_on: bool) -> None:
    h = _Harness(intents_on)
    first = "email Sarah the deck"

    async def _script() -> None:
        await h.barge_in_during(first)
        assert h.service._carry_user_text == first
        await h.turn(first, "wait what does that mean")

    h.run(_script)
    explain_call = h.calls[1]
    if intents_on:
        assert explain_call["query"] == "wait what does that mean"
        assert explain_call["mode"] == "fast", "an explanation starts no task"
        assert VOICE_EXPLAIN_INTERRUPTION_NOTE in str(explain_call["assistant_base_prompt"])
        assert h.service._carry_user_text == first, "the paused request is untouched"
    else:
        assert explain_call["query"] != "wait what does that mean"
        assert first in explain_call["query"]
        assert h.service._carry_user_text is None


@FLAG_STATES
def test_correction_revises_the_interrupted_request(intents_on: bool) -> None:
    h = _Harness(intents_on)
    first = "show revenue for this quarter"
    # An acknowledgement was already spoken, so nothing is carried today.
    h.first_turn_narration = "Let me check revenue."

    async def _script() -> None:
        await h.barge_in_during(first)
        assert h.service._carry_user_text is None
        await h.turn(first, "use last quarter instead")

    h.run(_script)
    if intents_on:
        assert h.calls[1]["query"] == "show revenue for this quarter (correction: use last quarter instead)"
    else:
        assert h.calls[1]["query"] == "use last quarter instead"


@FLAG_STATES
def test_correction_of_a_carried_request_is_merged_as_a_revision(intents_on: bool) -> None:
    h = _Harness(intents_on)
    first = "pull the Northwind renewal"

    async def _script() -> None:
        await h.barge_in_during(first)
        await h.turn(first, "no, Acme not Northwind")

    h.run(_script)
    if intents_on:
        assert h.calls[1]["query"] == "pull the Northwind renewal (correction: no, Acme not Northwind)"
    else:
        assert h.calls[1]["query"] == "pull the Northwind renewal, no, Acme not Northwind"


@FLAG_STATES
def test_speech_stop_turn_is_not_answered(intents_on: bool) -> None:
    h = _Harness(intents_on)

    async def _script() -> None:
        await h.barge_in_during("summarize the board deck")
        await h.turn("summarize the board deck", "stop talking")

    h.run(_script)
    assert len(h.calls) == (1 if intents_on else 2)


def test_a_silenced_reply_keeps_streaming_text_but_speaks_no_more() -> None:
    h = _Harness(True)

    async def _stream(**kwargs: Any):
        from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent

        h.calls.append(kwargs)
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "First part of the answer is here. "})
        h.session.mute_reply(h.service._reply_id)
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Second part arrives after the stop. "})
        yield AssistantStreamComplete(
            full_content="First part of the answer is here. Second part arrives after the stop.",
            tool_results=[],
            react_result=None,
            model="test",
        )

    h._stream = _stream  # type: ignore[method-assign]

    async def _script() -> None:
        await h.turn("read me the summary")

    h.run(_script)
    spoken = "".join(call.args[0] for call in h.service._push_llm_text.await_args_list)
    assert "First part" in spoken
    assert "Second part" not in spoken, "nothing more of a silenced reply is spoken"
    assert "Second part" in h.spoken_client_text(), "its text still reaches the client"
    assert h.persisted and "Second part" in h.persisted[-1]["assistant_text"], "normal completion path"


def _write_ctx() -> SimpleNamespace:
    return SimpleNamespace(org_id=ORG, conversation_id=CONV, settings=None)


@FLAG_STATES
def test_task_cancel_blocks_pending_writes_and_reports_what_already_happened(intents_on: bool) -> None:
    h = _Harness(intents_on, conversation_id=CONV)
    first = "email Sarah the deck and update the CRM"
    blocked: list[bool] = []

    def _first_write_completes() -> None:
        handle = voice_barge_in_write.begin_write_effect(_write_ctx(), "email.send")
        voice_barge_in_write.finish_write_effect(handle, "completed")

    h.during_first_turn = _first_write_completes

    async def _script() -> None:
        await h.barge_in_during(first)
        # A write of the interrupted work reaches its commit after the barge-in.
        try:
            voice_barge_in_write.begin_write_effect(_write_ctx(), "crm.update")
        except ToolValidationError:
            blocked.append(True)
        await h.turn(first, "cancel it")

    h.run(_script)
    assert blocked == [True], "the barge-in refused the pending write"
    if intents_on:
        assert len(h.calls) == 1, "'cancel it' is answered from the record, not by the brain"
        report = h.spoken_client_text()
        assert "email send" in report and "already gone through" in report
        assert "doesn't undo" in report, "never claims the email was unsent"
        assert "crm update" in report and "before it was sent" in report
        assert "undone" not in report.lower()
        # The stop stays armed for anything of the cancelled work still in flight.
        assert chat_turn_cancel_service.is_stop_requested(ORG, CONV) is True
        assert h.service._carry_user_text is None
        assert h.persisted and h.persisted[-1]["user_text"] == "cancel it"
    else:
        assert [c["query"] for c in h.calls] == [first, "cancel it"]
        assert chat_turn_cancel_service.is_stop_requested(ORG, CONV) is False


def test_task_cancel_with_nothing_done_says_so() -> None:
    assert describe_cancelled_work(completed=[], unconfirmed=[], blocked=[]) == (
        "Okay, cancelled. Nothing had been sent or changed yet."
    )
    in_flight = describe_cancelled_work(completed=[], unconfirmed=["email.send"], blocked=[])
    assert "can't confirm" in in_flight and "email send" in in_flight


def test_next_ordinary_turn_after_a_cancel_releases_the_stop() -> None:
    h = _Harness(True, conversation_id=CONV)

    async def _script() -> None:
        await h.barge_in_during("email Sarah the deck")
        await h.turn("email Sarah the deck", "cancel it")
        assert chat_turn_cancel_service.is_stop_requested(ORG, CONV) is True
        await h.turn("email Sarah the deck", "cancel it", "what's on my calendar today")

    h.run(_script)
    assert [c["query"] for c in h.calls][-1] == "what's on my calendar today"
    assert chat_turn_cancel_service.is_stop_requested(ORG, CONV) is False
