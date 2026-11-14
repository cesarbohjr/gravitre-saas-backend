"""V2 deterministic commit barrier: mid-sentence pauses must not speak early."""
from __future__ import annotations

import pytest
from pipecat.frames.frames import (
    EagerEndOfTurnCancelFrame,
    EagerTranscriptionFrame,
    InterimTranscriptionFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.base_object import BaseObject
from pipecat.utils.asyncio.task_manager import TaskManager

from app.services.pipecat_voice.committed_turn_barrier import CommittedTurnBarrierProcessor


async def _run(frames, *, clock=None):
    barrier = CommittedTurnBarrierProcessor(**({"clock": clock} if clock is not None else {}))
    await BaseObject.setup(barrier, TaskManager())
    delivered = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        delivered.append((frame, direction))

    barrier.push_frame = capture
    for frame in frames:
        await barrier.process_frame(frame, FrameDirection.DOWNSTREAM)
    return [f for f, direction in delivered if direction == FrameDirection.DOWNSTREAM], barrier


@pytest.mark.asyncio
@pytest.mark.parametrize("pause_ms", [400, 800, 1200])
async def test_mid_sentence_eager_candidate_never_commits_until_final(pause_ms):
    start = ProposedUserStartedSpeakingFrame()
    prefix = InterimTranscriptionFrame("Could you check the", "u1", "interim")
    eager = EagerTranscriptionFrame("Could you check the", "u1", f"eager-{pause_ms}")
    stop = ProposedUserStoppedSpeakingFrame()
    continued = InterimTranscriptionFrame("Could you check the report tomorrow", "u1", "new")
    cancelled = EagerEndOfTurnCancelFrame()
    final = TranscriptionFrame("Could you check the report tomorrow", "u1", "final", finalized=True)
    actual_stop = ProposedUserStoppedSpeakingFrame()

    delivered, barrier = await _run([start, prefix, eager, stop, continued, cancelled, final, actual_stop])
    assert eager not in delivered
    assert stop not in delivered
    assert final in delivered and actual_stop in delivered
    assert delivered.index(final) < delivered.index(actual_stop)
    assert barrier.suppressed_eager_count == 1


@pytest.mark.asyncio
async def test_eager_candidate_holds_stop_until_authoritative_final():
    start = ProposedUserStartedSpeakingFrame()
    eager = EagerTranscriptionFrame("What time is it", "u1", "eager")
    stop = ProposedUserStoppedSpeakingFrame()
    final = TranscriptionFrame("What time is it", "u1", "final", finalized=True)
    delivered, barrier = await _run([start, eager, stop, final])
    assert eager not in delivered
    assert delivered == [start, final, stop]
    assert barrier.suppressed_eager_count == 1


@pytest.mark.asyncio
async def test_new_turn_rejects_prior_speculative_stop():
    eager = EagerTranscriptionFrame("Actually", "u1", "eager")
    stale_stop = ProposedUserStoppedSpeakingFrame()
    restarted = ProposedUserStartedSpeakingFrame()
    final = TranscriptionFrame("Actually, use next week", "u1", "final", finalized=True)
    real_stop = ProposedUserStoppedSpeakingFrame()
    delivered, _ = await _run([eager, stale_stop, restarted, final, real_stop])
    assert eager not in delivered and stale_stop not in delivered
    assert delivered == [restarted, final, real_stop]


@pytest.mark.asyncio
async def test_non_eager_final_and_stop_pass_without_delay():
    final = TranscriptionFrame("hello", "u1", "final", finalized=True)
    stop = ProposedUserStoppedSpeakingFrame()
    delivered, _ = await _run([final, stop])
    assert delivered == [final, stop]


@pytest.mark.asyncio
async def test_upstream_eager_is_not_modified():
    frame = EagerTranscriptionFrame("hello", "u1", "eager")
    barrier = CommittedTurnBarrierProcessor()
    await BaseObject.setup(barrier, TaskManager())
    emitted = []

    async def capture(item, direction=FrameDirection.DOWNSTREAM):
        emitted.append((item, direction))

    barrier.push_frame = capture
    await barrier.process_frame(frame, FrameDirection.UPSTREAM)
    assert emitted == [(frame, FrameDirection.UPSTREAM)]
    assert barrier.suppressed_eager_count == 0


@pytest.mark.asyncio
async def test_probable_stop_before_eager_transcript_is_not_a_commit():
    """Ordering between the stop proposal and eager transcript can vary."""
    start = ProposedUserStartedSpeakingFrame()
    early_stop = ProposedUserStoppedSpeakingFrame()
    eager = EagerTranscriptionFrame("Show me", "u1", "candidate")
    cancel = EagerEndOfTurnCancelFrame()
    final = TranscriptionFrame("Show me the complete chart", "u1", "final", finalized=True)
    committed_stop = ProposedUserStoppedSpeakingFrame()
    delivered, _ = await _run([start, early_stop, eager, cancel, final, committed_stop])
    assert early_stop not in delivered
    assert eager not in delivered
    assert delivered == [start, cancel, final, committed_stop]


@pytest.mark.asyncio
async def test_stop_without_any_eager_frame_waits_for_final():
    """Native end-of-turn must not precede its authoritative transcript."""
    start = ProposedUserStartedSpeakingFrame()
    candidate_stop = ProposedUserStoppedSpeakingFrame()
    final = TranscriptionFrame("Done speaking", "u1", "final", finalized=True)
    delivered, _ = await _run([start, candidate_stop, final])
    assert delivered == [start, final, candidate_stop]


def test_live_flux_pipeline_positions_barrier_after_speculation_before_turn_aggregator():
    import inspect
    from app.services.pipecat_voice import pipeline

    source = inspect.getsource(pipeline.build_pipecat_voice_task)
    listing = source[source.index("pipeline = Pipeline("):]
    assert listing.index("            speculative,") < listing.index("CommittedTurnBarrierProcessor(")
    assert listing.index("CommittedTurnBarrierProcessor(") < listing.index("            user_agg,")


@pytest.mark.asyncio
@pytest.mark.parametrize("pause_ms", [400, 800, 1200])
async def test_virtual_clock_measures_full_speculative_stop_hold(pause_ms):
    """No provisional stop can reach the model during the measured pause."""
    simulated_time = [0.0]
    barrier = CommittedTurnBarrierProcessor(clock=lambda: simulated_time[0])
    await BaseObject.setup(barrier, TaskManager())
    forwarded = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        forwarded.append((frame, direction))

    barrier.push_frame = capture
    start = ProposedUserStartedSpeakingFrame()
    early = EagerTranscriptionFrame("Please show", "u1", "early")
    held_stop = ProposedUserStoppedSpeakingFrame()
    final = TranscriptionFrame("Please show the complete report", "u1", "final", finalized=True)
    for frame in (start, early, held_stop):
        await barrier.process_frame(frame, FrameDirection.DOWNSTREAM)
    assert [f for f, _ in forwarded] == [start]
    assert barrier.last_stop_hold_ms is None

    simulated_time[0] += pause_ms / 1000.0
    # Time has moved; candidate stop still cannot start a reply.
    assert [f for f, _ in forwarded] == [start]
    await barrier.process_frame(final, FrameDirection.DOWNSTREAM)
    assert [f for f, _ in forwarded] == [start, final, held_stop]
    assert barrier.last_stop_hold_ms == pytest.approx(pause_ms)


@pytest.mark.asyncio
async def test_duplicate_native_stop_cannot_start_two_assistant_turns():
    start = ProposedUserStartedSpeakingFrame()
    final = TranscriptionFrame("What changed today", "u1", "final", finalized=True)
    stop = ProposedUserStoppedSpeakingFrame()
    duplicate_stop = ProposedUserStoppedSpeakingFrame()
    delivered, _ = await _run([start, final, stop, duplicate_stop])
    assert delivered == [start, final, stop]


@pytest.mark.asyncio
async def test_second_real_utterance_may_commit_after_first_stop():
    one = ProposedUserStartedSpeakingFrame()
    first = TranscriptionFrame("yes", "u1", "first", finalized=True)
    stop1 = ProposedUserStoppedSpeakingFrame()
    two = ProposedUserStartedSpeakingFrame()
    second = TranscriptionFrame("and tomorrow too", "u1", "second", finalized=True)
    stop2 = ProposedUserStoppedSpeakingFrame()
    delivered, _ = await _run([one, first, stop1, two, second, stop2])
    assert delivered == [one, first, stop1, two, second, stop2]


@pytest.mark.asyncio
async def test_retransmitted_final_does_not_repeat_llm_context_or_stop():
    start = ProposedUserStartedSpeakingFrame()
    original = TranscriptionFrame("Give me the status", "u1", "same-final", finalized=True)
    retry = TranscriptionFrame("Give me the status", "u1", "same-final", finalized=True)
    stop = ProposedUserStoppedSpeakingFrame()
    stop_again = ProposedUserStoppedSpeakingFrame()
    delivered, _ = await _run([start, original, retry, stop, stop_again])
    assert delivered == [start, original, stop]


@pytest.mark.asyncio
async def test_repeating_same_words_in_distinct_final_turns_is_not_dropped():
    first_start = ProposedUserStartedSpeakingFrame()
    first = TranscriptionFrame("yes", "u1", "turn-1", finalized=True)
    first_stop = ProposedUserStoppedSpeakingFrame()
    next_start = ProposedUserStartedSpeakingFrame()
    second = TranscriptionFrame("yes", "u1", "turn-2", finalized=True)
    second_stop = ProposedUserStoppedSpeakingFrame()
    delivered, _ = await _run([
        first_start, first, first_stop, next_start, second, second_stop,
    ])
    assert delivered == [first_start, first, first_stop, next_start, second, second_stop]


@pytest.mark.asyncio
async def test_dropped_filler_final_releases_stop_for_empty_turn_cleanup():
    """UtteranceGate removes 'um'; stop must not remain pending indefinitely."""
    from types import SimpleNamespace

    session = SimpleNamespace(filler_finals_dropped=0)
    barrier = CommittedTurnBarrierProcessor(voice_session=session)
    await BaseObject.setup(barrier, TaskManager())
    delivered = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        delivered.append(frame)

    barrier.push_frame = capture
    start = ProposedUserStartedSpeakingFrame()
    eager = EagerTranscriptionFrame("um", "u1", "eager")
    stop = ProposedUserStoppedSpeakingFrame()
    await barrier.process_frame(start, FrameDirection.DOWNSTREAM)
    await barrier.process_frame(eager, FrameDirection.DOWNSTREAM)
    # The real UtteranceGate consumed the final and recorded the filler drop.
    session.filler_finals_dropped += 1
    await barrier.process_frame(stop, FrameDirection.DOWNSTREAM)
    assert delivered == [start, stop]
    assert barrier._pending_stop is None


@pytest.mark.asyncio
async def test_filler_drop_from_previous_turn_does_not_release_current_stop():
    from types import SimpleNamespace

    session = SimpleNamespace(filler_finals_dropped=2)
    barrier = CommittedTurnBarrierProcessor(voice_session=session)
    await BaseObject.setup(barrier, TaskManager())
    delivered = []

    async def capture(frame, direction=FrameDirection.DOWNSTREAM):
        delivered.append(frame)

    barrier.push_frame = capture
    start = ProposedUserStartedSpeakingFrame()
    stop = ProposedUserStoppedSpeakingFrame()
    await barrier.process_frame(start, FrameDirection.DOWNSTREAM)
    await barrier.process_frame(stop, FrameDirection.DOWNSTREAM)
    assert delivered == [start]
    final = TranscriptionFrame("yes", "u1", "t", finalized=True)
    await barrier.process_frame(final, FrameDirection.DOWNSTREAM)
    assert delivered == [start, final, stop]


def test_actual_pipeline_instruments_flux_commits_and_outbound_pcm():
    import inspect
    from app.services.pipecat_voice import pipeline

    source = inspect.getsource(pipeline.build_pipecat_voice_task)
    listing = source[source.index("pipeline = Pipeline("):]
    assert "VoiceTurnAudioEvidence()" in source
    assert "evidence=boundary_evidence, voice_session=voice_session" in source
    assert "OutboundAudioEvidenceProcessor(" in listing
    assert listing.index("CommittedTurnBarrierProcessor(") < listing.index("user_agg,")
    assert listing.index("OutboundAudioEvidenceProcessor(") > listing.index("*playout_processors,")
    # Match the actual pipeline element, not an earlier comment mentioning transport.output().
    assert listing.index("OutboundAudioEvidenceProcessor(") < listing.index("\n            transport.output(),")
