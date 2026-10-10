"""voice_confirmation_hold_v1: a bare go-ahead is acted on only once it is final.

Root cause of S8 "yes... wait" sending the email: Flux committed "yes" on the
pause and the brain started at once. The resumed "wait" opened a turn while
the brain was thinking; Flux sends its words only at EndOfTurn, so the
thinking-window grace (0.6 s) ran out with no words and resolved as a hold
(nothing to interrupt), and the late "wait" transcript was then neither held
nor treated as an interruption. The send went out first.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from pipecat.frames.frames import (
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services.pipecat_voice.backchannel_classifier import is_bare_confirmation
from app.services.pipecat_voice.backchannel_turn_strategy import BackchannelAwareUserTurnStartStrategy
from app.services.pipecat_voice.cognitive_llm import (
    answers_assistant_question,
    confirmation_hold_seconds,
)
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession


@pytest.mark.parametrize(
    "text",
    ["yes", "Yes.", "yeah go ahead", "send it", "Sure, send it now.", "ok do it", "yes please", "go ahead and send it", "yep"],
)
def test_bare_confirmations(text: str) -> None:
    assert is_bare_confirmation(text)


@pytest.mark.parametrize(
    "text",
    ["yes wait", "yes hold on", "yes but change the subject", "no", "wait", "what is it", "yes, send it to Mike instead"],
)
def test_not_bare_confirmations(text: str) -> None:
    assert not is_bare_confirmation(text)


ASKED = [
    {"role": "user", "content": "draft the follow-up email to Sarah"},
    {"role": "assistant", "content": "I've drafted it. Want me to send it now?"},
]


def test_yes_to_a_question_is_held_and_nothing_else_is() -> None:
    assert answers_assistant_question("yes", ASKED)
    assert answers_assistant_question("yeah go ahead", ASKED + [{"role": "user", "content": "yes"}])
    told = [ASKED[0], {"role": "assistant", "content": "Sent it to Sarah."}]
    assert not answers_assistant_question("yes", told)
    assert not answers_assistant_question("what's on my calendar today", ASKED)
    assert not answers_assistant_question("yes", [])


def test_hold_is_on_by_default_capped_and_switchable() -> None:
    assert confirmation_hold_seconds(SimpleNamespace()) == 0.6
    assert confirmation_hold_seconds(SimpleNamespace(voice_incomplete_turn_hold_ms=5000)) == 0.7
    assert confirmation_hold_seconds(SimpleNamespace(voice_confirmation_hold_v1=False)) == 0.0


def test_setting_defaults_on() -> None:
    from app.config import Settings

    assert Settings.model_fields["voice_confirmation_hold_v1"].default is True


# --- turn strategy: a wordless hold whose words turn out to be a stop ----------


def _transcription(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="u1", timestamp="2026-10-10T00:00:00Z")


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


async def _thinking_strategy():
    session = VoicePipelineSession()
    session.assistant_generating = True
    strategy = BackchannelAwareUserTurnStartStrategy(
        enable_interruptions=True, grace_period_s=0.05, voice_session=session
    )
    await BaseObject.setup(strategy, TaskManager())
    recorder = _Recorder()
    strategy.add_event_handler("on_user_turn_started", recorder.on_user_turn_started)
    strategy.add_event_handler("on_reset_aggregation", recorder.on_reset_aggregation)
    strategy.add_event_handler("on_push_frame", recorder._noop)
    strategy.add_event_handler("on_broadcast_frame", recorder._noop)
    return strategy, recorder, session


@pytest.mark.asyncio
async def test_late_stop_words_after_a_wordless_hold_are_escalated() -> None:
    strategy, recorder, session = await _thinking_strategy()
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    assert session.user_speaking
    await asyncio.sleep(0.15)  # grace runs out with no words: held as noise
    assert recorder.turn_started_calls[0].enable_interruptions is False
    await strategy.process_frame(_transcription("wait"))
    assert session.held_speech_escalations == 1
    assert recorder.reset_aggregation_calls == 0, "the words stay: they are the next turn"
    await strategy.process_frame(ProposedUserStoppedSpeakingFrame())
    assert not session.user_speaking
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_late_filler_after_a_wordless_hold_stays_held() -> None:
    strategy, recorder, session = await _thinking_strategy()
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    await asyncio.sleep(0.15)
    await strategy.process_frame(_transcription("you there?"))
    assert session.held_speech_escalations == 0
    assert recorder.reset_aggregation_calls == 1
    await strategy.cleanup()
