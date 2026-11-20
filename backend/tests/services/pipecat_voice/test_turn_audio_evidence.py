"""V2 evidence for provider false finals and observable server PCM output."""
from __future__ import annotations

import pytest
from pipecat.frames.frames import (
    EagerEndOfTurnCancelFrame,
    EagerTranscriptionFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.base_object import BaseObject
from pipecat.utils.asyncio.task_manager import TaskManager

from app.services.pipecat_voice.committed_turn_barrier import CommittedTurnBarrierProcessor
from app.services.pipecat_voice.turn_audio_evidence import (
    OutboundAudioEvidenceProcessor, VoiceTurnAudioEvidence,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("pause_ms", [400, 800, 1200])
async def test_flux_hard_false_final_is_observable_but_not_invisibly_fixed(pause_ms):
    """A *provider final* during a pause is different from probable-EOT.

    A later fresh start within the observation window marks it suspect.
    The barrier intentionally does not claim it can know the provider was wrong
    until subsequent user speech arrives. No provider calls or browser playback.
    """
    now = [0.0]
    evidence = VoiceTurnAudioEvidence(clock=lambda: now[0], resume_window_s=1.5)
    barrier = CommittedTurnBarrierProcessor(clock=lambda: now[0], evidence=evidence)
    await BaseObject.setup(barrier, TaskManager())
    pushed = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        pushed.append(frame)

    barrier.push_frame = capture
    first = ProposedUserStartedSpeakingFrame()
    premature = TranscriptionFrame("What about the", "u1", "partial-final", finalized=True)
    stop = ProposedUserStoppedSpeakingFrame()
    resume = ProposedUserStartedSpeakingFrame()
    continuation = TranscriptionFrame("remainder of the report", "u1", "continued-final", finalized=True)
    new_stop = ProposedUserStoppedSpeakingFrame()

    for frame in (first, premature, stop):
        await barrier.process_frame(frame, FrameDirection.DOWNSTREAM)
    assert pushed == [first, premature, stop]
    assert evidence.snapshot()["suspected_false_finals"] == 0
    now[0] += pause_ms / 1000.0
    for frame in (resume, continuation, new_stop):
        await barrier.process_frame(frame, FrameDirection.DOWNSTREAM)
    assert pushed == [first, premature, stop, resume, continuation, new_stop]
    result = evidence.snapshot()
    assert result["suspected_false_finals"] == 1
    assert result["provider_finals"] == 2
    assert result["committed_stops"] == 2


def test_audio_timing_and_no_transcript_in_snapshot():
    t = [0.0]
    e = VoiceTurnAudioEvidence(clock=lambda: t[0])
    e.new_start()
    e.eager()
    e.eager_cancel()
    e.audio()
    assert e.audio_without_committed_stop == 1
    e.final()
    t[0] = 0.2
    e.stop()
    t[0] = 0.35
    e.audio()
    assert e.snapshot()["first_audio_after_stop_ms"] == pytest.approx(150.0)
    assert e.outbound_audio_frames == 2
    assert set(e.snapshot()) == {
        "epoch", "eager_candidates", "eager_cancelled", "provider_finals",
        "committed_stops", "duplicate_finals", "duplicate_stops",
        "suspected_false_finals", "suspected_false_finals_with_audio",
        "outbound_audio_frames",
        "audio_without_committed_stop", "first_audio_after_stop_ms",
    }


def test_later_independent_turn_does_not_look_like_false_final():
    t = [0.0]
    e = VoiceTurnAudioEvidence(clock=lambda: t[0])
    e.new_start()
    e.final()
    e.stop()
    t[0] = 3.0
    e.new_start()
    assert e.snapshot()["suspected_false_finals"] == 0


@pytest.mark.asyncio
async def test_real_pcm_tap_propagates_frames_and_records_sanitized_trace():
    class Trace:
        def __init__(self):
            self.extras = []

        def add_extra(self, key, value):
            self.extras.append((key, value))

    evidence = VoiceTurnAudioEvidence(clock=lambda: 1.0)
    trace = Trace()
    tap = OutboundAudioEvidenceProcessor(evidence=evidence, turn_trace=trace)
    await BaseObject.setup(tap, TaskManager())
    emitted = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        emitted.append((frame, direction))

    tap.push_frame = capture
    pcm = TTSAudioRawFrame(b"\\x00\\x00" * 160, 16000, 1)
    await tap.process_frame(pcm, FrameDirection.DOWNSTREAM)
    assert emitted == [(pcm, FrameDirection.DOWNSTREAM)]
    assert evidence.outbound_audio_frames == 1
    assert evidence.audio_without_committed_stop == 1
    assert trace.extras[0][0] == "voice_boundary_audio"
    assert "transcript" not in repr(trace.extras[0][1]).lower()
    assert "audio" not in trace.extras[0][1].keys()  # counters only, no PCM bytes


@pytest.mark.asyncio
async def test_hard_false_final_identifies_audio_emitted_before_continuation():
    """A hard Flux final can trigger output before the next spoken clause."""
    t = [0.0]
    evidence = VoiceTurnAudioEvidence(clock=lambda: t[0])
    barrier = CommittedTurnBarrierProcessor(clock=lambda: t[0], evidence=evidence)
    await BaseObject.setup(barrier, TaskManager())
    sent = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        sent.append(frame)

    barrier.push_frame = capture
    for frame in (
        ProposedUserStartedSpeakingFrame(),
        TranscriptionFrame("What about the", "u1", "first", finalized=True),
        ProposedUserStoppedSpeakingFrame(),
    ):
        await barrier.process_frame(frame, FrameDirection.DOWNSTREAM)
    t[0] = 0.25
    evidence.audio()  # Real output tap records the server PCM frame.
    t[0] = 0.4
    await barrier.process_frame(ProposedUserStartedSpeakingFrame(), FrameDirection.DOWNSTREAM)
    result = evidence.snapshot()
    assert result["suspected_false_finals"] == 1
    assert result["suspected_false_finals_with_audio"] == 1
    assert result["outbound_audio_frames"] == 1
    # Detection alone cannot retract speech already handed to transport.
    assert result["first_audio_after_stop_ms"] is None  # reset for new epoch
