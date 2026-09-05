"""Phase 6 (conversational-realism): GravitreVoiceLatencyObserver on the live Flux path.

Real, live-framework tests using actual Pipecat frame classes and the actual
``UserBotLatencyObserver`` base class - not a hand-rolled fake. Confirms the
root-cause fix: the stock observer only starts its clock on
``VADUserStoppedSpeakingFrame`` (a frame Flux, which has no VAD stacked, never
emits - see ``pipeline.py``), so without this subclass, live voice latency
signals would silently never fire.
"""
from __future__ import annotations

import asyncio
import time

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.observers.base_observer import FramePushed
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.frame_processor import FrameDirection

from app.services.pipecat_voice.voice_latency_observer import GravitreVoiceLatencyObserver


def _pushed(frame, *, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> FramePushed:
    return FramePushed(
        source=None,  # type: ignore[arg-type]
        destination=None,  # type: ignore[arg-type]
        frame=frame,
        direction=direction,
        timestamp=0,
    )


async def _observer() -> GravitreVoiceLatencyObserver:
    obs = GravitreVoiceLatencyObserver()
    obs._register_event_handler("on_latency_measured")
    obs._register_event_handler("on_latency_breakdown")
    obs._register_event_handler("on_first_bot_speech_latency")
    return obs


class TestFluxPathStartsTheClock:
    @pytest.mark.asyncio
    async def test_proposed_user_stopped_speaking_starts_measurement_stock_class_misses(self):
        """MUTATION PROOF: without the ProposedUserStoppedSpeakingFrame branch,
        _user_stopped_time stays None forever on the Flux path (no VAD stacked),
        so on_latency_measured/on_latency_breakdown would never fire live.
        """
        obs = await _observer()
        measured: list[float] = []
        obs.add_event_handler("on_latency_measured", lambda _o, secs: measured.append(secs))

        await obs.on_push_frame(_pushed(ProposedUserStoppedSpeakingFrame()))
        assert obs._user_stopped_time is not None

        await obs.on_push_frame(_pushed(BotStartedSpeakingFrame()))
        # on_latency_measured handlers run as spawned tasks (BaseObject's
        # non-sync event dispatch), not inline — yield once for it to run.
        await asyncio.sleep(0.05)
        assert len(measured) == 1
        assert measured[0] >= 0

    @pytest.mark.asyncio
    async def test_stock_vad_stopped_frame_still_works_unmodified(self):
        """Non-Flux (VAD) paths must keep behaving exactly as the stock class does."""
        obs = await _observer()
        measured: list[float] = []
        obs.add_event_handler("on_latency_measured", lambda _o, secs: measured.append(secs))

        frame = VADUserStoppedSpeakingFrame(stop_secs=0.4)
        frame.timestamp = time.time()
        await obs.on_push_frame(_pushed(frame))
        assert obs._user_stopped_time is not None

        await obs.on_push_frame(_pushed(BotStartedSpeakingFrame()))
        await asyncio.sleep(0.05)
        assert len(measured) == 1

    @pytest.mark.asyncio
    async def test_first_proposal_wins_not_overwritten_by_a_second(self):
        obs = await _observer()
        await obs.on_push_frame(_pushed(ProposedUserStoppedSpeakingFrame()))
        first = obs._user_stopped_time
        await obs.on_push_frame(_pushed(ProposedUserStoppedSpeakingFrame()))
        assert obs._user_stopped_time == first

    @pytest.mark.asyncio
    async def test_upstream_frames_are_ignored(self):
        obs = await _observer()
        await obs.on_push_frame(
            _pushed(ProposedUserStoppedSpeakingFrame(), direction=FrameDirection.UPSTREAM)
        )
        assert obs._user_stopped_time is None

    @pytest.mark.asyncio
    async def test_proposed_user_started_speaking_resets_stale_pending_state(self):
        """MUTATION PROOF: a fresh user turn beginning (e.g. after a suppressed
        backchannel - Phase 1) must discard a stale timestamp, or a later
        completed turn would report a bogus, inflated latency measured from
        the wrong starting point.
        """
        obs = await _observer()
        await obs.on_push_frame(_pushed(ProposedUserStoppedSpeakingFrame()))
        assert obs._user_stopped_time is not None

        await obs.on_push_frame(_pushed(ProposedUserStartedSpeakingFrame()))
        assert obs._user_stopped_time is None


def test_pipeline_task_accepts_the_subclass_as_an_observer():
    """Confirms GravitreVoiceLatencyObserver is a drop-in for PipelineTask's
    observers=[...] kwarg — the exact call shape used in pipeline.py — with a
    real Pipeline/PipelineTask construction, not a mock."""
    obs = GravitreVoiceLatencyObserver()
    task = PipelineTask(Pipeline([]), observers=[obs])
    assert obs in task._observer._observers  # type: ignore[attr-defined]
