"""voice_interrupt_intents_v1: a wordless start that runs out its wait while work runs.

Flux sends the words only at EndOfTurn, so "why is it taking so long" over the
running task's narration had no text when the wordless wait ran out. It was
taken for an interruption, which cancelled the running task (bench S13b/S14).
Now the reply is silenced at that moment (as fast as before), the work keeps
running, and the final words decide: an explanation is an aside, a backchannel
or "stop talking" keeps the work, a stop, cancel, correction or new request is
the interruption it always was. No words at all within the bound: interruption.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    InterruptionFrame,
    ProposedUserStartedSpeakingFrame,
)
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services.pipecat_voice import backchannel_turn_strategy
from app.services.pipecat_voice.backchannel_turn_strategy import (
    BackchannelAwareUserTurnStartStrategy,
)
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from app.services.turn_cancellation import TurnCancellation
from tests.services.pipecat_voice.test_interrupt_intents import (  # noqa: F401 - autouse fixture
    _final,
    _isolated,
    _Recorder,
)


def _session(*, work_active: bool = True) -> tuple[VoicePipelineSession, list[str], list[str], TurnCancellation]:
    session = VoicePipelineSession()
    session.explain_aside_enabled = True
    session.work_active = work_active
    work = TurnCancellation()
    session.bind_turn_work(work)
    asides: list[str] = []
    silenced: list[str] = []

    def _start(text: str) -> bool:
        asides.append(text)
        return True

    async def _silence() -> bool:
        silenced.append("silenced")
        return True

    session.aside_handler = _start
    session.speech_aside_handler = _silence
    session.speech_stop_handler = _silence
    return session, asides, silenced, work


async def _timed_out_start(session: VoicePipelineSession, *, intents_on: bool = True):
    """The bot is speaking; the user starts; no words arrive before the wait runs out."""
    strategy = BackchannelAwareUserTurnStartStrategy(
        enable_interruptions=True,
        grace_period_s=0.01,
        max_wordless_wait_s=0.02,
        gravitre_settings=SimpleNamespace(voice_interrupt_intents_v1=intents_on),
        voice_session=session,
    )
    await BaseObject.setup(strategy, TaskManager())
    rec = _Recorder()
    for name in ("on_user_turn_started", "on_reset_aggregation", "on_push_frame", "on_broadcast_frame"):
        strategy.add_event_handler(name, getattr(rec, name))
    await strategy.process_frame(BotStartedSpeakingFrame())
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    for _ in range(50):
        await asyncio.sleep(0.01)
        if not strategy._pending:
            break
    assert not strategy._pending, "the wordless wait ran out"
    return strategy, rec


@pytest.mark.asyncio
async def test_the_wait_running_out_silences_the_reply_but_keeps_the_work() -> None:
    session, _, silenced, work = _session()
    strategy, rec = await _timed_out_start(session)
    assert silenced == ["silenced"], "the user is heard at once: the reply stops"
    assert InterruptionFrame not in rec.broadcasts, "nothing cancels the running task yet"
    assert rec.started[-1].enable_interruptions is False
    assert not work.cancelled
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_an_explanation_becomes_an_aside_and_the_task_keeps_running() -> None:
    session, asides, _, work = _session()
    strategy, rec = await _timed_out_start(session)
    await strategy.process_frame(_final("why is it taking so long"))
    assert asides == ["why is it taking so long"]
    assert InterruptionFrame not in rec.broadcasts
    assert rec.resets == 1, "the words never become a turn"
    assert not work.cancelled
    await strategy.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["mm-hmm", "right", "stop talking"])
async def test_a_backchannel_or_speech_stop_keeps_the_work(text: str) -> None:
    session, asides, _, work = _session()
    strategy, rec = await _timed_out_start(session)
    await strategy.process_frame(_final(text))
    assert asides == []
    assert InterruptionFrame not in rec.broadcasts
    assert rec.resets == 1
    assert not work.cancelled
    await strategy.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["cancel it", "stop", "no, use last quarter instead"])
async def test_a_stop_cancel_or_correction_cancels_the_task(text: str) -> None:
    session, asides, _, work = _session()
    strategy, rec = await _timed_out_start(session)
    await strategy.process_frame(_final(text))
    assert asides == []
    assert InterruptionFrame in rec.broadcasts
    assert work.cancelled
    assert rec.resets == 0, "the words are the next turn"
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_a_new_request_is_an_interruption() -> None:
    session, asides, _, _work = _session()
    strategy, rec = await _timed_out_start(session)
    await strategy.process_frame(_final("show me revenue by region for last year"))
    assert asides == []
    assert InterruptionFrame in rec.broadcasts
    assert rec.resets == 0
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_no_words_within_the_bound_falls_back_to_an_interruption(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backchannel_turn_strategy, "WORDLESS_HOLD_MAX_S", 0.05)
    session, _, _, _work = _session()
    strategy, rec = await _timed_out_start(session)
    assert InterruptionFrame not in rec.broadcasts
    await asyncio.sleep(0.15)
    assert InterruptionFrame in rec.broadcasts
    assert not strategy._held_wordless
    await strategy.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize(("intents_on", "work_active"), [(False, True), (True, False)], ids=["flag_off", "no_work"])
async def test_without_the_flag_or_running_work_the_wait_running_out_interrupts(
    intents_on: bool, work_active: bool
) -> None:
    session, _, silenced, _work = _session(work_active=work_active)
    strategy, rec = await _timed_out_start(session, intents_on=intents_on)
    assert silenced == []
    assert rec.started[-1].enable_interruptions is True, "today's interruption"
    assert not strategy._held_wordless
    await strategy.cleanup()
