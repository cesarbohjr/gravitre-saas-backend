"""Regressions from the 2026-10-08 live voice test: ignored turns and slow barge-in.

Flux opens every user turn with an InterruptionFrame, including when the bot
is idle. Those used to arm the conversation stop marker on every turn; the
next answer (a speculative run in particular) read the marker, returned an
empty "cancelled" completion, and the user heard nothing.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services import chat_turn_cancel_service
from app.services.pipecat_voice.cognitive_llm import adopt_or_fresh
from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from tests.support.fake_supabase import FakeSupabase

ORG = "00000000-0000-4000-8000-0000000000a1"
USER = "00000000-0000-4000-8000-0000000000c3"
SETTINGS = SimpleNamespace()


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    client = FakeSupabase()
    monkeypatch.setattr("app.workflows.repository.get_supabase_client", lambda _s: client)
    monkeypatch.setattr("app.routers.assistant.get_supabase_client", lambda _s: client)
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    chat_turn_cancel_service._local_stops.clear()
    return client


async def _reporter(**kwargs: Any) -> tuple[ElevenLabsInterruptReporter, list[Frame]]:
    reporter = ElevenLabsInterruptReporter(
        reconcile_played_audio_enabled=True,
        settings=SETTINGS,
        org_id=ORG,
        user_id=USER,
        **kwargs,
    )
    await BaseObject.setup(reporter, TaskManager())
    pushed: list[Frame] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        pushed.append(frame)

    reporter.push_frame = _capture  # type: ignore[method-assign]
    return reporter, pushed


def _interrupted_messages(pushed: list[Frame]) -> list[dict[str, Any]]:
    return [
        f.message
        for f in pushed
        if isinstance(f, OutputTransportMessageUrgentFrame)
        and isinstance(f.message, dict)
        and f.message.get("type") == "speech.interrupted"
    ]


def _stopped(conv: str) -> bool:
    return chat_turn_cancel_service.is_stop_requested(ORG, conv, settings=SETTINGS)


@pytest.mark.asyncio
async def test_user_turn_while_bot_idle_is_not_a_barge_in(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    reporter, pushed = await _reporter(conversation_id=conv)

    # Previous reply fully generated and played out.
    await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await reporter.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
    await reporter.process_frame(BotStartedSpeakingFrame(), FrameDirection.UPSTREAM)
    await reporter.process_frame(BotStoppedSpeakingFrame(), FrameDirection.UPSTREAM)

    # User says "how are you?" -> Flux opens the turn with an interruption.
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    await reporter.settle_barge_in()

    assert isinstance(pushed[-1], InterruptionFrame)
    assert _interrupted_messages(pushed) == []
    assert not _stopped(conv), "an idle user turn armed the stop marker"


@pytest.mark.asyncio
async def test_barge_in_while_bot_speaks_still_stops_and_reports(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    reporter, pushed = await _reporter(conversation_id=conv)
    reporter.begin_turn("Walk me through the plan")

    await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await reporter.process_frame(BotStartedSpeakingFrame(), FrameDirection.UPSTREAM)
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)

    assert len(_interrupted_messages(pushed)) == 1
    # Stop marker is armed for in-flight writes, then released by the next turn.
    for task in list(reporter._post_interrupt_tasks):
        await task
    assert _stopped(conv)
    await reporter.settle_barge_in()
    assert not _stopped(conv)


@pytest.mark.asyncio
async def test_socket_close_releases_a_stop_marker(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    chat_turn_cancel_service.request_stop(ORG, conv, settings=SETTINGS)
    reporter, _ = await _reporter(conversation_id=conv)
    await reporter.release_stop_marker()
    assert not _stopped(conv)


@pytest.mark.asyncio
async def test_answer_expected_after_the_question_was_heard() -> None:
    session = VoicePipelineSession()
    reporter, _ = await _reporter(voice_session=session)
    draft = "I found three open deals. Want me to draft follow-ups for them?"

    class _Ledger:
        ever_recorded = True
        heard = ""

        def snapshot(self) -> str:
            return self.heard

        def reset(self) -> None:
            pass

    ledger = _Ledger()
    reporter._spoken_ledger = ledger
    await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await reporter.process_frame(
        OutputTransportMessageUrgentFrame(message={"type": "assistant_text", "delta": draft}),
        FrameDirection.DOWNSTREAM,
    )
    ledger.heard = "I found three"
    assert session.expects_answer() is False
    ledger.heard = draft
    assert session.expects_answer() is True


async def _events(*items: Any):
    for item in items:
        yield item


def _delta(text: str) -> AssistantStreamEvent:
    return AssistantStreamEvent(sse_type="text-delta", payload={"delta": text})


@pytest.mark.asyncio
async def test_cancelled_empty_speculation_falls_back_to_a_fresh_answer() -> None:
    cancelled = AssistantStreamComplete(
        full_content="", tool_results=[], react_result=None, model="cancelled"
    )
    fresh_done = AssistantStreamComplete(
        full_content="I'm doing well.", tool_results=[], react_result=None, model="gpt"
    )
    out = [
        e
        async for e in adopt_or_fresh(
            _events(cancelled), lambda: _events(_delta("I'm doing well."), fresh_done)
        )
    ]
    assert out[-1] is fresh_done
    assert any(isinstance(e, AssistantStreamEvent) for e in out)


@pytest.mark.asyncio
async def test_adopted_speculation_with_text_is_used_as_is() -> None:
    done = AssistantStreamComplete(full_content="Hi!", tool_results=[], react_result=None, model="gpt")

    def _fresh():
        raise AssertionError("fresh call must not run")

    out = [e async for e in adopt_or_fresh(_events(_delta("Hi!"), done), _fresh)]
    assert out[-1] is done
