"""Real, live-framework tests for the backchannel-aware turn start strategy.

Conversational-realism Phase 1. These tests exercise the actual Pipecat
frame classes, the actual pipecat.turns event-handler machinery, and the
actual asyncio grace-window task - not a hand-rolled fake. Only the full
``UserTurnController``/pipeline plumbing is bypassed, since the strategy is
the unit under test.
"""
from __future__ import annotations

import asyncio

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.turns.types import ProcessFrameResult
from pipecat.turns.user_start.base_user_turn_start_strategy import UserTurnStartedParams
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services.pipecat_voice.backchannel_classifier import BackchannelClassification
from app.services.pipecat_voice.backchannel_turn_strategy import (
    BackchannelAwareUserTurnStartStrategy,
)


def _transcription(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="u1", timestamp="2026-09-04T00:00:00Z")


class _Recorder:
    """Captures every on_user_turn_started / on_reset_aggregation call."""

    def __init__(self):
        self.turn_started_calls: list[UserTurnStartedParams] = []
        self.reset_aggregation_calls = 0

    async def on_user_turn_started(self, _strategy, params: UserTurnStartedParams):
        self.turn_started_calls.append(params)

    async def on_reset_aggregation(self, _strategy):
        self.reset_aggregation_calls += 1

    async def on_push_frame(self, _strategy, _frame, _direction=None):
        pass

    async def on_broadcast_frame(self, _strategy, _frame_cls, **_kwargs):
        pass


async def _make_strategy(*, grace_period_s: float = 0.9) -> tuple[BackchannelAwareUserTurnStartStrategy, _Recorder]:
    decisions = []

    async def _capture(decision):
        decisions.append(decision)

    strategy = BackchannelAwareUserTurnStartStrategy(
        enable_interruptions=True,
        grace_period_s=grace_period_s,
        on_classification=_capture,
    )
    strategy.decisions = decisions  # type: ignore[attr-defined]

    await BaseObject.setup(strategy, TaskManager())

    recorder = _Recorder()
    strategy.add_event_handler("on_user_turn_started", recorder.on_user_turn_started)
    strategy.add_event_handler("on_reset_aggregation", recorder.on_reset_aggregation)
    strategy.add_event_handler("on_push_frame", recorder.on_push_frame)
    strategy.add_event_handler("on_broadcast_frame", recorder.on_broadcast_frame)
    return strategy, recorder


class TestBotNotSpeakingPassThrough:
    @pytest.mark.asyncio
    async def test_normal_turn_start_resolves_immediately_when_bot_silent(self):
        """MUTATION PROOF: if the bot-speaking gate were removed/inverted, a
        normal turn (bot not talking) would be needlessly delayed by the
        grace window - the common case must stay instant.
        """
        strategy, recorder = await _make_strategy()
        result = await strategy.process_frame(ProposedUserStartedSpeakingFrame())

        assert result is ProcessFrameResult.STOP
        assert len(recorder.turn_started_calls) == 1
        params = recorder.turn_started_calls[0]
        assert params.enable_interruptions is True
        assert params.enable_user_speaking_frames is True
        await strategy.cleanup()


class TestBackchannelSuppression:
    @pytest.mark.asyncio
    async def test_backchannel_utterance_does_not_broadcast_interruption(self):
        strategy, recorder = await _make_strategy()

        await strategy.process_frame(BotStartedSpeakingFrame())
        result = await strategy.process_frame(ProposedUserStartedSpeakingFrame())
        assert result is ProcessFrameResult.STOP
        # Not resolved yet - held pending while bot is speaking.
        assert recorder.turn_started_calls == []

        await strategy.process_frame(_transcription("uh-huh"))

        assert len(recorder.turn_started_calls) == 1
        params = recorder.turn_started_calls[0]
        assert params.enable_interruptions is False, "MUTATION PROOF: backchannel must never interrupt"
        assert params.enable_user_speaking_frames is False
        assert recorder.reset_aggregation_calls == 1, (
            "MUTATION PROOF: backchannel text must be dropped from LLM context"
        )
        assert strategy.decisions[-1].classification is BackchannelClassification.BACKCHANNEL
        await strategy.cleanup()

    @pytest.mark.asyncio
    async def test_backchannel_resolved_via_stop_proposal_if_no_transcript_yet(self):
        """Even if the final transcript race loses to the stop proposal, the
        strategy still classifies (on whatever text is buffered) rather than
        hanging the turn open forever.
        """
        strategy, recorder = await _make_strategy(grace_period_s=5.0)

        await strategy.process_frame(BotStartedSpeakingFrame())
        await strategy.process_frame(ProposedUserStartedSpeakingFrame())
        await strategy.process_frame(_transcription("okay"))
        await strategy.process_frame(ProposedUserStoppedSpeakingFrame())

        assert len(recorder.turn_started_calls) == 1
        assert recorder.turn_started_calls[0].enable_interruptions is False
        await strategy.cleanup()


class TestGenuineInterruptionUnaffected:
    @pytest.mark.asyncio
    async def test_real_interruption_still_broadcasts(self):
        """MUTATION PROOF: a genuine interruption during agent speech must
        still open the turn with interruptions enabled - the existing
        barge-in mechanism must not regress.
        """
        strategy, recorder = await _make_strategy()

        await strategy.process_frame(BotStartedSpeakingFrame())
        await strategy.process_frame(ProposedUserStartedSpeakingFrame())
        await strategy.process_frame(
            _transcription("actually I need it sent to Sarah instead")
        )

        assert len(recorder.turn_started_calls) == 1
        params = recorder.turn_started_calls[0]
        assert params.enable_interruptions is True
        assert params.enable_user_speaking_frames is True
        assert recorder.reset_aggregation_calls == 0
        assert strategy.decisions[-1].classification is BackchannelClassification.CORRECTION
        await strategy.cleanup()

    @pytest.mark.asyncio
    async def test_stop_command_still_interrupts(self):
        strategy, recorder = await _make_strategy()

        await strategy.process_frame(BotStartedSpeakingFrame())
        await strategy.process_frame(ProposedUserStartedSpeakingFrame())
        await strategy.process_frame(_transcription("stop"))

        assert recorder.turn_started_calls[0].enable_interruptions is True
        assert strategy.decisions[-1].classification is BackchannelClassification.STOP_COMMAND
        await strategy.cleanup()

    @pytest.mark.asyncio
    async def test_grace_window_timeout_defaults_to_interruption_not_suppression(self):
        """MUTATION PROOF: if no transcript ever arrives, ambiguity must
        resolve to the SAFE side (let the agent be interrupted), never to
        silently swallowing a real interruption forever.
        """
        strategy, recorder = await _make_strategy(grace_period_s=0.05)

        await strategy.process_frame(BotStartedSpeakingFrame())
        await strategy.process_frame(ProposedUserStartedSpeakingFrame())
        # No transcript ever arrives before the (short, test-only) timeout.
        await asyncio.sleep(0.2)

        assert len(recorder.turn_started_calls) == 1
        assert recorder.turn_started_calls[0].enable_interruptions is True
        assert strategy.decisions[-1].resolved_by_timeout is True
        await strategy.cleanup()


class TestBotStoppedSpeakingResetsGate:
    @pytest.mark.asyncio
    async def test_after_bot_stops_speaking_turns_resolve_immediately_again(self):
        strategy, recorder = await _make_strategy()

        await strategy.process_frame(BotStartedSpeakingFrame())
        await strategy.process_frame(BotStoppedSpeakingFrame())

        result = await strategy.process_frame(ProposedUserStartedSpeakingFrame())
        assert result is ProcessFrameResult.STOP
        assert len(recorder.turn_started_calls) == 1
        assert recorder.turn_started_calls[0].enable_interruptions is True
        await strategy.cleanup()
