"""voice_overlap_duck_v1: duck the reply while an overlapping start is classified.

While the bot speaks, a proposed user-turn-start is held until words arrive
(Flux sends none before end of turn). With the flag on, the client is told to
duck the reply's audio for that hold (speech.duck) and to restore it
(speech.unduck) when the overlap was a backchannel or the bot's own echo. A
real interruption keeps the speech.interrupted path, which cuts and resets.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    OutputTransportMessageUrgentFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.turns.user_start.base_user_turn_start_strategy import UserTurnStartedParams
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services.pipecat_voice.backchannel_turn_strategy import (
    BackchannelAwareUserTurnStartStrategy,
)
from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession


def _final(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="u1", timestamp="2026-10-10T00:00:00Z")


class _Recorder:
    def __init__(self) -> None:
        self.turns: list[UserTurnStartedParams] = []
        self.broadcasts: list[type] = []

    async def on_user_turn_started(self, _s, params: UserTurnStartedParams) -> None:
        self.turns.append(params)

    async def on_reset_aggregation(self, _s) -> None:
        return None

    async def on_push_frame(self, *_a, **_k) -> None:
        return None

    async def on_broadcast_frame(self, _s, frame_cls, **_k) -> None:
        self.broadcasts.append(frame_cls)


async def _strategy(*, duck_on: bool, bot_speaking: bool = True):
    session = VoicePipelineSession()
    session.begin_reply()
    sent: list[bool] = []

    async def _duck(ducked: bool) -> None:
        sent.append(ducked)

    session.speech_duck_handler = _duck
    strategy = BackchannelAwareUserTurnStartStrategy(
        enable_interruptions=True,
        grace_period_s=5.0,
        max_wordless_wait_s=0.0,
        gravitre_settings=SimpleNamespace(voice_overlap_duck_v1=duck_on),
        voice_session=session,
    )
    await BaseObject.setup(strategy, TaskManager())
    rec = _Recorder()
    for name in ("on_user_turn_started", "on_reset_aggregation", "on_push_frame", "on_broadcast_frame"):
        strategy.add_event_handler(name, getattr(rec, name))
    if bot_speaking:
        await strategy.process_frame(BotStartedSpeakingFrame())
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    return strategy, rec, session, sent


@pytest.mark.asyncio
async def test_pending_start_while_speaking_ducks_once() -> None:
    strategy, rec, _session, sent = await _strategy(duck_on=True)
    assert sent == [True], "the overlap is ducked as soon as the hold begins"
    assert rec.turns == [], "still held for classification"
    # A second proposal during the same hold neither restarts nor re-ducks.
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    assert sent == [True]
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_backchannel_restores_the_reply() -> None:
    strategy, rec, _session, sent = await _strategy(duck_on=True)
    await strategy.process_frame(_final("uh-huh"))
    assert rec.turns and rec.turns[-1].enable_interruptions is False
    assert sent == [True, False], "a backchannel unducks; the reply goes on at full level"
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_own_voice_echo_restores_the_reply() -> None:
    strategy, rec, session, sent = await _strategy(duck_on=True)
    session.note_bot_speech("here is the website traffic for last month across every channel")
    await strategy.process_frame(_final("the website traffic for last month across"))
    assert rec.turns and rec.turns[-1].enable_interruptions is False
    assert sent == [True, False]
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_real_interruption_keeps_the_cut_path() -> None:
    strategy, rec, _session, sent = await _strategy(duck_on=True)
    await strategy.process_frame(_final("use last quarter instead"))
    assert rec.turns and rec.turns[-1].enable_interruptions is True
    # No unduck: speech.interrupted (sent by the reporter on the interruption)
    # flushes the reply and resets the client's gain; an unduck first would
    # bring the old reply back to full level for a moment.
    assert sent == [True]
    # The next overlap ducks again.
    await strategy.process_frame(BotStartedSpeakingFrame())
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    assert sent == [True, True]
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_reply_ending_during_the_duck_still_resolves() -> None:
    strategy, rec, _session, sent = await _strategy(duck_on=True)
    await strategy.process_frame(BotStoppedSpeakingFrame())
    await strategy.process_frame(_final("mm"))
    await strategy.process_frame(ProposedUserStoppedSpeakingFrame())
    # The pending start still resolves after the reply stopped, and the
    # backchannel restores the gain, so the next reply never starts ducked.
    assert rec.turns and rec.turns[-1].enable_interruptions is False
    assert sent == [True, False]
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_nothing_sent_when_the_bot_is_not_speaking() -> None:
    strategy, rec, _session, sent = await _strategy(duck_on=True, bot_speaking=False)
    assert rec.turns and rec.turns[-1].enable_interruptions is True, "pass-through turn start"
    assert sent == []
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_flag_off_sends_nothing() -> None:
    strategy, rec, _session, sent = await _strategy(duck_on=False)
    await strategy.process_frame(_final("uh-huh"))
    assert rec.turns and rec.turns[-1].enable_interruptions is False
    assert sent == []
    strategy2, _rec2, _s2, sent2 = await _strategy(duck_on=False)
    await strategy2.process_frame(_final("use last quarter instead"))
    assert sent2 == []
    await strategy.cleanup()
    await strategy2.cleanup()


@pytest.mark.asyncio
async def test_reporter_sends_duck_events_with_the_reply_id() -> None:
    session = VoicePipelineSession()
    reporter = ElevenLabsInterruptReporter(settings=SimpleNamespace(), voice_session=session)
    await BaseObject.setup(reporter, TaskManager())
    pushed: list[tuple[Frame, FrameDirection]] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        pushed.append((frame, direction))

    reporter.push_frame = _capture  # type: ignore[method-assign]
    assert session.speech_duck_handler == reporter.send_speech_duck
    session.begin_reply()
    session.begin_reply()
    await session.speech_duck_handler(True)
    await session.speech_duck_handler(False)
    assert [(f.message, d) for f, d in pushed if isinstance(f, OutputTransportMessageUrgentFrame)] == [
        ({"type": "speech.duck", "reply_id": 2}, FrameDirection.DOWNSTREAM),
        ({"type": "speech.unduck", "reply_id": 2}, FrameDirection.DOWNSTREAM),
    ]
    assert len(pushed) == 2, "ducking pushes no InterruptionFrame and nothing upstream"
