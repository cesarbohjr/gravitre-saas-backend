"""Bounded Flux hard-final stabilization: no premature approval or audio turn."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from pipecat.frames.frames import (
    InterruptionFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.base_object import BaseObject
from pipecat.utils.asyncio.task_manager import TaskManager

from app.services.pipecat_voice.final_turn_stability import (
    FinalTurnStabilityProcessor, is_short_confirmation,
)


class ManualSleep:
    def __init__(self):
        self.delays = []
        self.waiters = []

    async def __call__(self, duration):
        fut = asyncio.get_running_loop().create_future()
        self.delays.append(duration)
        self.waiters.append(fut)
        await fut

    def advance(self):
        for fut in self.waiters:
            if not fut.done():
                fut.set_result(None)


async def _build(*, session=None):
    sleep = ManualSleep()
    processor = FinalTurnStabilityProcessor(
        voice_session=session, sleeper=sleep,
    )
    await BaseObject.setup(processor, TaskManager())
    passed = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        passed.append(frame)

    processor.push_frame = capture
    return processor, sleep, passed


async def _pump():
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.mark.parametrize("pause_ms", [400, 800, 1200])
@pytest.mark.asyncio
async def test_hard_false_final_followed_by_continuation_is_not_spoken_early(pause_ms):
    """Pauses < approval window cannot let 'yes' be a stand-alone approval."""
    proc, clock, out = await _build()
    first_start = ProposedUserStartedSpeakingFrame()
    yes = TranscriptionFrame("yes", "u1", "yes-final", finalized=True)
    first_stop = ProposedUserStoppedSpeakingFrame()
    for frame in (first_start, yes, first_stop):
        await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    await _pump()
    assert out == [first_start]
    assert clock.delays == [1.2]
    # The tested pause is a logical event-time offset: the next start happens
    # BEFORE the grace timer fires; no real sleep and no fake measured SLO.
    assert pause_ms <= 1200
    continue_start = ProposedUserStartedSpeakingFrame()
    correction = TranscriptionFrame("wait, do not send", "u1", "continued", finalized=True)
    correction_stop = ProposedUserStoppedSpeakingFrame()
    for frame in (continue_start, correction, correction_stop):
        await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    await _pump()
    assert out == [first_start]
    assert proc.rejoined_segments == 1
    assert clock.delays[-1] == 1.2
    clock.advance()
    await _pump()
    assert out == [first_start, yes, correction, correction_stop]
    assert proc.released_turns == 1


@pytest.mark.asyncio
async def test_short_confirmation_is_delayed_but_not_lost():
    proc, clock, out = await _build()
    start = ProposedUserStartedSpeakingFrame()
    final = TranscriptionFrame("yes", "u", "final", finalized=True)
    stop = ProposedUserStoppedSpeakingFrame()
    for frame in (start, final, stop):
        await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    await _pump()
    assert clock.delays == [1.2]
    assert out == [start]
    clock.advance()
    await _pump()
    assert out == [start, final, stop]
    assert proc.released_turns == 1


@pytest.mark.asyncio
async def test_nonapproval_turn_uses_400ms_window():
    proc, clock, out = await _build()
    start = ProposedUserStartedSpeakingFrame()
    final = TranscriptionFrame("Explain the weather forecast", "u", "final", finalized=True)
    stop = ProposedUserStoppedSpeakingFrame()
    for frame in (start, final, stop):
        await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    await _pump()
    assert clock.delays == [0.4]
    clock.advance()
    await _pump()
    assert out == [start, final, stop]


@pytest.mark.asyncio
async def test_pending_approval_uses_longer_window_even_for_other_words():
    proc, clock, out = await _build(session=SimpleNamespace(pending_approval=object()))
    for frame in (
        ProposedUserStartedSpeakingFrame(),
        TranscriptionFrame("proceed", "u", "f", finalized=True),
        ProposedUserStoppedSpeakingFrame(),
    ):
        await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    await _pump()
    assert clock.delays == [1.2]
    clock.advance()
    await _pump()
    assert len(out) == 3


@pytest.mark.asyncio
async def test_interruption_passes_immediately_while_final_is_held():
    proc, clock, out = await _build()
    start = ProposedUserStartedSpeakingFrame()
    for frame in (
        start,
        TranscriptionFrame("show the results", "u", "f", finalized=True),
        ProposedUserStoppedSpeakingFrame(),
    ):
        await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    await _pump()
    interrupt = InterruptionFrame()
    await proc.process_frame(interrupt, FrameDirection.DOWNSTREAM)
    assert out == [start, interrupt]
    clock.advance()
    await _pump()
    assert len(out) == 4


@pytest.mark.asyncio
async def test_filtered_filler_stop_still_releases_original_yes():
    proc, clock, out = await _build()
    start = ProposedUserStartedSpeakingFrame()
    yes = TranscriptionFrame("yes", "u", "yes", finalized=True)
    for frame in (start, yes, ProposedUserStoppedSpeakingFrame()):
        await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    await _pump()
    await proc.process_frame(ProposedUserStartedSpeakingFrame(), FrameDirection.DOWNSTREAM)
    # The upstream UtteranceGate dropped "um": only a stop remains.
    last_stop = ProposedUserStoppedSpeakingFrame()
    await proc.process_frame(last_stop, FrameDirection.DOWNSTREAM)
    await _pump()
    clock.advance()
    await _pump()
    assert out == [start, yes, last_stop]


@pytest.mark.asyncio
async def test_real_repeated_turns_after_window_are_not_merged():
    proc, clock, out = await _build()
    first_start = ProposedUserStartedSpeakingFrame()
    first = TranscriptionFrame("yes", "u", "first", finalized=True)
    stop1 = ProposedUserStoppedSpeakingFrame()
    for frame in (first_start, first, stop1):
        await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    await _pump()
    clock.advance()
    await _pump()
    second_start = ProposedUserStartedSpeakingFrame()
    second = TranscriptionFrame("yes", "u", "second", finalized=True)
    stop2 = ProposedUserStoppedSpeakingFrame()
    for frame in (second_start, second, stop2):
        await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    await _pump()
    clock.advance()
    await _pump()
    assert out == [first_start, first, stop1, second_start, second, stop2]


@pytest.mark.asyncio
async def test_true_user_stop_frames_are_also_buffered():
    proc, clock, out = await _build()
    start = UserStartedSpeakingFrame()
    final = TranscriptionFrame("hello again", "u", "final", finalized=True)
    stop = UserStoppedSpeakingFrame()
    for frame in (start, final, stop):
        await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    await _pump()
    assert out == [start]
    clock.advance()
    await _pump()
    assert out == [start, final, stop]


@pytest.mark.parametrize("text", ["yes", "yes!", "go ahead", "send it", "approve", "ok"])
def test_short_confirmation_safety_classifier(text):
    assert is_short_confirmation(text)


def test_real_pipeline_places_stability_after_barrier_and_before_aggregator():
    import inspect
    from app.services.pipecat_voice import pipeline

    source = inspect.getsource(pipeline.build_pipecat_voice_task)
    listing = source[source.index("pipeline = Pipeline("):]
    assert listing.index("CommittedTurnBarrierProcessor(") < listing.index("FinalTurnStabilityProcessor(")
    assert listing.index("FinalTurnStabilityProcessor(") < listing.index("user_agg,")
    assert "if use_flux and settings.voice_final_stability_v2 else []" in source
