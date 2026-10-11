"""Meaningful interruptions: explain ("why?"), pause ("hold on"), resume ("go on").

explain  -> answered from the active task; the paused request stays carried
pause    -> speech stops, the work and request are kept, an unsent write waits
resume   -> the unheard rest is spoken, held writes go on; never an approval
cancel / expiry while paused -> held writes are refused and recorded as stopped
"""
from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import chat_turn_cancel_service, voice_barge_in_write, voice_pause_gate
from app.services.pipecat_voice.backchannel_classifier import (
    InterruptIntent,
    classify_interrupt_intent,
    is_bare_confirmation,
    is_pause_request,
    is_resume_request,
)
from app.services.pipecat_voice.cognitive_llm import VOICE_EXPLAIN_INTERRUPTION_NOTE
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from app.services.tool_types import ToolValidationError
from tests.services.pipecat_voice.test_interrupt_intents import _final, _Harness, _strategy

ORG = "00000000-0000-4000-8000-000000000001"
CONV = "00000000-0000-4000-8000-000000000003"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch):
    chat_turn_cancel_service.reset_local_stops_for_tests()
    voice_barge_in_write.reset_write_effects_for_tests()
    voice_pause_gate.reset_for_tests()
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    monkeypatch.setattr("app.services.pipecat_voice.voice_latency_metrics._write", lambda *a, **k: None)
    monkeypatch.setattr("app.services.voice_barge_in_write.action_is_mutating_write", lambda a: a == "email.send")
    yield
    voice_pause_gate.reset_for_tests()


# --- classification --------------------------------------------------------------------


@pytest.mark.parametrize("text", ["why?", "Why not?", "how come?", "wait, why?", "how so?", "what for?",
                                  "why's that?", "why are you sending it to her?", "why that one"])
def test_why_questions_are_explanations(text: str) -> None:
    assert classify_interrupt_intent(text) is InterruptIntent.EXPLAIN


@pytest.mark.parametrize("text", ["hold on", "hang on", "wait", "one sec", "give me a moment",
                                  "hold on a second", "just a sec", "pause"])
def test_hold_on_is_a_pause_not_a_stop(text: str) -> None:
    assert is_pause_request(text)
    assert classify_interrupt_intent(text) is InterruptIntent.PAUSE


@pytest.mark.parametrize(
    ("text", "intent"),
    [("stop", InterruptIntent.STOP), ("wait, cancel it", InterruptIntent.TASK_CANCEL),
     ("stop talking", InterruptIntent.SPEECH_STOP),
     ("hold on, use last quarter instead", InterruptIntent.CORRECTION)],
)
def test_pause_is_distinct_from_stop_cancel_and_correction(text: str, intent: InterruptIntent) -> None:
    assert classify_interrupt_intent(text) is intent


@pytest.mark.parametrize("text", ["go on", "continue", "okay, carry on", "keep going", "I'm back", "go ahead"])
def test_resume_phrases(text: str) -> None:
    assert is_resume_request(text)


def test_yes_is_not_a_resume_and_go_on_is_not_an_approval_while_paused() -> None:
    assert not is_resume_request("yes")
    # "go on" is a resume, not a bare confirmation, so it can never approve.
    assert not is_bare_confirmation("go on")


# --- the write gate --------------------------------------------------------------------


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(org_id=ORG, conversation_id=CONV, settings=None)


def _write_in_thread(results: list[Any]) -> threading.Thread:
    def _run() -> None:
        try:
            handle = voice_barge_in_write.begin_write_effect(_ctx(), "email.send")
            results.append(("started", time.monotonic(), handle))
        except ToolValidationError as exc:
            results.append(("refused", time.monotonic(), str(exc)))

    thread = threading.Thread(target=_run)
    thread.start()
    return thread


def test_a_write_waits_while_paused_and_proceeds_on_resume() -> None:
    voice_pause_gate.pause(ORG, CONV)
    results: list[Any] = []
    thread = _write_in_thread(results)
    time.sleep(0.3)
    assert results == [], "nothing is sent while paused"
    resumed_at = time.monotonic()
    voice_pause_gate.resume(ORG, CONV)
    thread.join(2)
    assert results and results[0][0] == "started" and results[0][1] >= resumed_at


def test_cancel_during_a_pause_refuses_the_held_write() -> None:
    voice_pause_gate.pause(ORG, CONV)
    results: list[Any] = []
    thread = _write_in_thread(results)
    time.sleep(0.2)
    voice_pause_gate.end_pause(ORG, CONV)
    thread.join(2)
    assert results[0][0] == "refused"
    effects = voice_barge_in_write.write_effects_since(ORG, CONV, 0)
    assert effects[-1]["status"] == voice_barge_in_write.STATUS_BLOCKED, "reported as stopped, truthfully"


def test_an_expired_pause_refuses_the_held_write() -> None:
    voice_pause_gate.pause(ORG, CONV, max_s=0.3)
    results: list[Any] = []
    _write_in_thread(results).join(2)
    assert results[0][0] == "refused"
    assert not voice_pause_gate.is_paused(ORG, CONV)


def test_a_stop_armed_during_the_pause_refuses_the_write_even_after_resume() -> None:
    voice_pause_gate.pause(ORG, CONV)
    results: list[Any] = []
    thread = _write_in_thread(results)
    time.sleep(0.2)
    chat_turn_cancel_service.request_stop(ORG, CONV, owner="conn")
    thread.join(2)
    assert results[0][0] == "refused"


def test_a_paused_write_on_the_event_loop_is_refused_not_blocked() -> None:
    voice_pause_gate.pause(ORG, CONV)

    async def _on_loop() -> str:
        try:
            voice_barge_in_write.begin_write_effect(_ctx(), "email.send")
            return "started"
        except ToolValidationError:
            return "refused"

    assert asyncio.run(_on_loop()) == "refused"


def test_reads_are_never_held() -> None:
    voice_pause_gate.pause(ORG, CONV)
    assert voice_barge_in_write.begin_write_effect(_ctx(), "analytics.report") is None


# --- turn taking -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hold_on_pauses_without_interrupting_and_go_on_resumes() -> None:
    session = VoicePipelineSession()
    calls: list[str] = []

    async def _pause() -> bool:
        calls.append("pause")
        session.paused_reply = {"reply_id": 0, "heard_chars": 0}
        return True

    async def _resume() -> bool:
        calls.append("resume")
        session.paused_reply = None
        return True

    session.pause_handler = _pause
    session.resume_handler = _resume
    strategy, rec, _ = await _strategy(True, session)
    await strategy.process_frame(_final("hold on"))
    assert calls == ["pause"]
    assert rec.started[-1].enable_interruptions is False, "the work is not cancelled"
    assert rec.resets == 1 and rec.broadcasts == []
    await strategy.process_frame(_final("one sec"))
    assert calls == ["pause"] and rec.resets == 2, "still paused"
    await strategy.process_frame(_final("okay go on"))
    assert calls == ["pause", "resume"] and rec.resets == 3
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_a_new_request_after_hold_on_becomes_a_turn() -> None:
    from pipecat.frames.frames import InterruptionFrame

    session = VoicePipelineSession()

    async def _pause() -> bool:
        session.paused_reply = {"reply_id": 0, "heard_chars": 0}
        return True

    session.pause_handler = _pause
    strategy, rec, _ = await _strategy(True, session)
    await strategy.process_frame(_final("hold on"))
    await strategy.process_frame(_final("actually send it to Mike instead"))
    assert rec.broadcasts == [InterruptionFrame]
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_with_the_flag_off_hold_on_is_an_ordinary_interruption() -> None:
    session = VoicePipelineSession()
    paused: list[bool] = []

    async def _pause() -> bool:
        paused.append(True)
        return True

    session.pause_handler = _pause
    strategy, rec, _ = await _strategy(False, session)
    await strategy.process_frame(_final("hold on"))
    assert paused == [] and rec.started[-1].enable_interruptions is True
    await strategy.cleanup()


def test_reporter_resume_starts_from_the_sentence_it_stopped_in() -> None:
    from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter

    reporter = ElevenLabsInterruptReporter(voice_session=VoicePipelineSession())
    reporter._draft_client = "Traffic was up 12 percent. Most of it came from search. Paid was flat."
    heard = len("Traffic was up 12 percent. Most of it")
    assert reporter.paused_remainder({"heard_chars": heard}) == "Most of it came from search. Paid was flat."
    assert reporter.paused_remainder({"heard_chars": 10_000}) == ""


# --- explain and the carried request ---------------------------------------------------


def test_why_after_an_acknowledgement_keeps_the_request_and_explains_from_the_task() -> None:
    h = _Harness(True)
    first = "pull the ads report for last week"
    h.first_turn_narration = "Okay, one moment."

    async def _script() -> None:
        await h.barge_in_during(first)
        assert h.service._carry_user_text == first, "an acknowledgement is not an answer"
        await h.turn(first, "wait, why?")
        assert h.service._carry_user_text == first, "the explanation does not drop the request"
        await h.turn(first, "wait, why?", "okay go on")

    h.run(_script)
    explain_prompt = str(h.calls[1].get("assistant_base_prompt") or "")
    assert h.calls[1]["query"] == "wait, why?"
    assert VOICE_EXPLAIN_INTERRUPTION_NOTE in explain_prompt
    assert f"Paused request (not done yet): {first}" in explain_prompt
    # "go on" continues the paused request instead of losing it.
    assert first in h.calls[2]["query"]


def test_stop_after_an_acknowledgement_drops_the_request() -> None:
    h = _Harness(True)
    first = "pull the ads report for last week"
    h.first_turn_narration = "Okay, one moment."

    async def _script() -> None:
        await h.barge_in_during(first)
        await h.turn(first, "stop")

    h.run(_script)
    assert h.calls[-1]["query"] == "stop"


def test_a_new_turn_ends_the_pause_and_refuses_held_writes() -> None:
    h = _Harness(True, conversation_id=CONV)

    async def _script() -> None:
        h.session.paused_reply = {"reply_id": 0, "heard_chars": 0}
        voice_pause_gate.pause(ORG, CONV)
        await h.turn("what's on my calendar")

    h.run(_script)
    assert h.session.paused_reply is None and not voice_pause_gate.is_paused(ORG, CONV)


def test_go_on_as_a_turn_resumes_and_skips_the_brain() -> None:
    h = _Harness(True, conversation_id=CONV)

    async def _script() -> None:
        h.reporter._draft_client = "Your total is 1,250 dollars. It is due Friday."
        h.session.paused_reply = {"reply_id": 0, "heard_chars": 5}
        voice_pause_gate.pause(ORG, CONV)
        await h.turn("go on")

    h.run(_script)
    assert h.calls == []
    assert not voice_pause_gate.is_paused(ORG, CONV)
    assert h.session.paused_reply is None


@pytest.mark.parametrize(
    ("text", "intent"),
    [("huh?", InterruptIntent.EXPLAIN), ("what?", InterruptIntent.EXPLAIN), ("sorry?", InterruptIntent.EXPLAIN),
     ("okay stop", InterruptIntent.STOP), ("stop please", InterruptIntent.STOP), ("huh", InterruptIntent.BACKCHANNEL)],
)
def test_did_not_catch_and_lead_in_stop(text: str, intent: InterruptIntent) -> None:
    assert classify_interrupt_intent(text) is intent


@pytest.mark.asyncio
async def test_a_bare_stop_waits_only_briefly_for_more_words() -> None:
    """IT-5: interim "stop" used to hold the reply for the whole 1.8 s wordless window."""
    from pipecat.frames.frames import ProposedUserStartedSpeakingFrame

    from app.services.pipecat_voice.backchannel_turn_strategy import (
        SPEECH_STOP_CONTINUATION_WAIT_S,
        BackchannelAwareUserTurnStartStrategy,
    )
    from pipecat.utils.asyncio.task_manager import TaskManager
    from pipecat.utils.base_object import BaseObject
    from pipecat.frames.frames import BotStartedSpeakingFrame
    from tests.services.pipecat_voice.test_interrupt_intents import _interim, _Recorder

    strategy = BackchannelAwareUserTurnStartStrategy(
        enable_interruptions=True,
        grace_period_s=0.05,
        max_wordless_wait_s=1.8,
        gravitre_settings=SimpleNamespace(voice_interrupt_intents_v1=True),
        voice_session=VoicePipelineSession(),
    )
    await BaseObject.setup(strategy, TaskManager())
    rec = _Recorder()
    for name in ("on_user_turn_started", "on_reset_aggregation", "on_push_frame", "on_broadcast_frame"):
        strategy.add_event_handler(name, getattr(rec, name))
    await strategy.process_frame(BotStartedSpeakingFrame())
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    started = time.monotonic()
    await strategy.process_frame(_interim("stop"))
    while not rec.started and time.monotonic() - started < 2.5:
        await asyncio.sleep(0.02)
    waited = time.monotonic() - started
    assert rec.started and rec.started[-1].enable_interruptions is True
    assert waited < SPEECH_STOP_CONTINUATION_WAIT_S + 0.4, waited
    await strategy.cleanup()
