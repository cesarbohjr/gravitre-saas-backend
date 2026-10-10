"""Follow-ups to barge-in handling found by the voice scenario bench.

- An adopted speculative run is cancelled with the turn a barge-in cut off,
  so the brain call behind it can never commit a write afterwards (on by
  default).
- "Mm-hmm." while the bot talks: the utterance gate drops it as filler before
  the turn strategy sees any words; it must not count as an interruption (on
  by default).
- "Stop talking, keep working" (voice_interrupt_intents_v1): the silenced
  work's result is delivered once, spoken under a new reply id when the user
  has not moved on, otherwise shown only.
- voice_incomplete_turn_hold_v1: a committed final cut off mid-thought holds
  its first output briefly; a resume inside the hold carries the fragment
  into the next turn.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from pipecat.frames.frames import (
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services.pipecat_voice.backchannel_classifier import is_syntactically_incomplete
from app.services.pipecat_voice.cognitive_llm import (
    INCOMPLETE_TURN_HOLD_MAX_S,
    incomplete_turn_hold_seconds,
    merge_unanswered_turn,
)
from app.services.pipecat_voice.speculative_generation import (
    SpeculativeGenerationCoordinator,
    start_speculative_run,
)
from app.services.pipecat_voice.utterance_gate import UtteranceGateProcessor
from tests.services.pipecat_voice.speculation_helpers import (
    adoptable,
    confirmed_turn_sees_matching_versions,
)
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from tests.services.pipecat_voice.test_interrupt_intents import (  # noqa: F401 - autouse fixture
    FLAG_STATES,
    _ctx,
    _final,
    _Harness,
    _isolated,
    _strategy,
)

# --- 1. adopted speculative run vs barge-in (default on) --------------------------


def _adoptable_run(h: _Harness, text: str, writes: list[str], *, commit_after_s: float):
    """A speculative brain run for ``text`` that commits a write ``commit_after_s`` in."""
    from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent

    async def _runner():
        yield AssistantStreamEvent(sse_type="data-intelligence", payload={"data": {}})
        await asyncio.sleep(commit_after_s)
        writes.append("crm.update")
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Done, all twelve moved."})
        yield AssistantStreamComplete(full_content="Done, all twelve moved.", tool_results=[], react_result=None, model="t")

    coordinator = SpeculativeGenerationCoordinator()
    run = start_speculative_run(text=text, runner=_runner, create_task=asyncio.create_task)
    coordinator.set_run(adoptable(run))
    h.service._speculative_coordinator = coordinator
    return run


def test_barge_in_cancels_the_adopted_run_so_its_write_never_lands() -> None:
    h = _Harness(False)
    writes: list[str] = []
    text = "yes go ahead and move them all"

    async def _script() -> None:
        run = _adoptable_run(h, text, writes, commit_after_s=2.0)
        await BaseObject.setup(h.reporter, TaskManager())
        task = asyncio.create_task(h.service.process_frame(_ctx(text), FrameDirection.DOWNSTREAM))
        await asyncio.sleep(0.3)
        assert run.outcome == "adopted"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # The next turn releases the stop marker; the run must already be gone.
        await asyncio.sleep(3.0)
        assert run.task.cancelled() or run.task.done()

    with confirmed_turn_sees_matching_versions():
        h.run(_script)
    assert writes == [], "a run cut off by a barge-in never commits afterwards"


def test_an_adopted_run_that_finishes_normally_is_unaffected() -> None:
    h = _Harness(False)
    writes: list[str] = []
    text = "yes go ahead and move them all"

    async def _script() -> None:
        _adoptable_run(h, text, writes, commit_after_s=0.1)
        await h.turn(text)

    with confirmed_turn_sees_matching_versions():
        h.run(_script)
    assert writes == ["crm.update"], "an approved write in a turn nobody interrupted still lands"
    assert h.service._adopted_run is None


# --- 2. gate-dropped "Mm-hmm." during playback (default on) -----------------------


@pytest.mark.asyncio
async def test_utterance_gate_reports_dropped_filler_to_the_session() -> None:
    session = VoicePipelineSession()
    gate = UtteranceGateProcessor(app_settings=None, org_id="o", voice_session=session)
    pushed: list[Any] = []

    async def _push(frame, direction=FrameDirection.DOWNSTREAM):
        pushed.append(frame)

    gate.push_frame = _push  # type: ignore[method-assign]

    async def _noop(*_a, **_k):
        return None

    with patch("pipecat.processors.frame_processor.FrameProcessor.process_frame", new=_noop):
        await gate.process_frame(_final("Mm-hmm."), FrameDirection.DOWNSTREAM)
        await gate.process_frame(_final("x"), FrameDirection.DOWNSTREAM)
        await gate.process_frame(_final("what about last week"), FrameDirection.DOWNSTREAM)
    assert session.filler_finals_dropped == 1, "only filler counts, not other non-utterances"
    assert [f.text for f in pushed if isinstance(f, TranscriptionFrame)] == ["what about last week"]


@pytest.mark.asyncio
@FLAG_STATES
async def test_mm_hmm_dropped_by_the_gate_does_not_interrupt_the_bot(intents_on: bool) -> None:
    session = VoicePipelineSession()
    strategy, rec, _ = await _strategy(intents_on, session)
    # The gate dropped the final; only the end of the utterance arrives.
    session.note_filler_dropped()
    await strategy.process_frame(ProposedUserStoppedSpeakingFrame())
    assert rec.started[-1].enable_interruptions is False, "a backchannel never interrupts"
    assert rec.started[-1].enable_user_speaking_frames is False
    await strategy.cleanup()


@pytest.mark.asyncio
@FLAG_STATES
async def test_a_wordless_start_without_dropped_filler_still_interrupts(intents_on: bool) -> None:
    strategy, rec, _ = await _strategy(intents_on)
    await strategy.process_frame(ProposedUserStoppedSpeakingFrame())
    assert rec.started[-1].enable_interruptions is True, "unclassified speech is never suppressed"
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_filler_dropped_before_the_start_does_not_count() -> None:
    session = VoicePipelineSession()
    session.note_filler_dropped()  # an earlier "uh", before this utterance
    strategy, rec, _ = await _strategy(False, session)
    await strategy.process_frame(ProposedUserStoppedSpeakingFrame())
    assert rec.started[-1].enable_interruptions is True
    await strategy.cleanup()


# --- 3. "stop talking, keep working": deliver the result once ---------------------


def _silenced_work_harness(*, user_moves_on: bool) -> tuple[_Harness, list[Any]]:
    h = _Harness(True)

    async def _stream(**kwargs: Any):
        from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent

        h.calls.append(kwargs)
        await h.service._speak_narration("Let me check the pipeline report.")
        # "Stop talking, keep working" lands while the tool runs.
        h.session.note_user_turn_start()
        h.session.mute_reply(h.service._reply_id)
        await h.service._speak_narration("Still checking the pipeline report.")
        if user_moves_on:
            h.session.note_user_turn_start()
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "The pipeline is one point eight million."})
        yield AssistantStreamComplete(
            full_content="The pipeline is one point eight million.", tool_results=[], react_result=None, model="t"
        )

    h._stream = _stream  # type: ignore[method-assign]
    return h, []


def _pushed(h: _Harness, cls) -> list[Any]:
    return [c.args[0] for c in h.service.push_frame.await_args_list if isinstance(c.args[0], cls)]


def test_silenced_work_result_is_spoken_under_a_new_reply_when_the_user_waited() -> None:
    h, _ = _silenced_work_harness(user_moves_on=False)

    async def _script() -> None:
        await h.turn("pull the pipeline report")

    h.run(_script)
    spoken = "".join(call.args[0] for call in h.service._push_llm_text.await_args_list)
    assert "Still checking" not in spoken, "narration after the stop stays silent"
    assert spoken.count("The pipeline is one point eight million.") == 1, "result spoken once"
    starts = _pushed(h, LLMFullResponseStartFrame)
    assert [getattr(f, "gravitre_reply_id", None) for f in starts] == [1, 2]
    assert len(_pushed(h, LLMFullResponseEndFrame)) == 2, "the silenced reply is closed before the result"
    assert not h.session.reply_muted(2) and h.session.reply_muted(1)
    assert h.persisted[-1]["assistant_text"] == "The pipeline is one point eight million."


def test_silenced_work_result_is_only_shown_when_the_user_moved_on() -> None:
    h, _ = _silenced_work_harness(user_moves_on=True)

    async def _script() -> None:
        await h.turn("pull the pipeline report")

    h.run(_script)
    spoken = "".join(call.args[0] for call in h.service._push_llm_text.await_args_list)
    assert "one point eight" not in spoken, "nothing is spoken over a user who went on"
    assert "one point eight million" in h.spoken_client_text(), "the result is shown"
    assert len(_pushed(h, LLMFullResponseStartFrame)) == 1
    assert h.persisted[-1]["assistant_text"] == "The pipeline is one point eight million."


@FLAG_STATES
def test_speculation_skips_speech_stop_and_cancel_only_with_the_flag(intents_on: bool) -> None:
    from app.services.pipecat_voice.speculative_prefetch import SpeculativePrefetchProcessor

    coordinator = SpeculativeGenerationCoordinator()
    proc = SpeculativePrefetchProcessor(
        app_settings=SimpleNamespace(voice_interrupt_intents_v1=intents_on),
        org_id="o",
        user_id="u",
        speculative_coordinator=coordinator,
    )
    started: list[str] = []

    def _fake_set_run(run):
        started.append(run.text)
        run.task.cancel()

    coordinator.set_run = _fake_set_run  # type: ignore[method-assign]

    async def _script() -> None:
        await BaseObject.setup(proc, TaskManager())
        for text in ("stop talking, keep working", "okay cancel that please", "show me the pipeline"):
            proc._last_partial = text
            proc._last_speculative_text = None
            proc._start_speculative_generation()
        await asyncio.sleep(0)

    asyncio.run(_script())
    assert "show me the pipeline" in started
    assert "okay cancel that please" not in started, "a cancellation is never speculated on"
    assert ("stop talking, keep working" in started) is (not intents_on)


# --- 4. voice_incomplete_turn_hold_v1 ------------------------------------------------


@pytest.mark.parametrize(
    ("text", "incomplete"),
    [
        ("I want to check", True),
        ("I want to check.", True),
        ("compare it to the", True),
        ("send it to Mike and", True),
        ("so...", True),
        ("I was thinking, um", True),
        ("what's the traffic?", False),
        ("last month's traffic", False),
        ("pull the pipeline report for this quarter", False),
        ("cancel it", False),
    ],
)
def test_syntactically_incomplete_finals(text: str, incomplete: bool) -> None:
    assert is_syntactically_incomplete(text) is incomplete


def test_hold_is_off_by_default_and_capped() -> None:
    assert incomplete_turn_hold_seconds(SimpleNamespace()) == 0.0
    assert incomplete_turn_hold_seconds(SimpleNamespace(voice_incomplete_turn_hold_v1=True)) == 0.6
    assert (
        incomplete_turn_hold_seconds(
            SimpleNamespace(voice_incomplete_turn_hold_v1=True, voice_incomplete_turn_hold_ms=5000)
        )
        == INCOMPLETE_TURN_HOLD_MAX_S
    )


def test_a_fragment_is_joined_not_replaced() -> None:
    merged, _ = merge_unanswered_turn("I want to check", "last month's traffic", [], fragment=True)
    assert merged == "I want to check last month's traffic"


def _hold_harness(hold_on: bool, *, resume_after_s: float | None) -> _Harness:
    h = _Harness(False)
    h.settings.voice_incomplete_turn_hold_v1 = hold_on

    async def _stream(**kwargs: Any):
        from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent

        h.calls.append(kwargs)
        if len(h.calls) == 1 and resume_after_s is not None:
            loop = asyncio.get_running_loop()
            loop.call_later(resume_after_s, h.session.note_user_turn_start)
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Sure, what should I check?"})
        yield AssistantStreamComplete(
            full_content="Sure, what should I check?", tool_results=[], react_result=None, model="t"
        )

    h._stream = _stream  # type: ignore[method-assign]
    return h


@pytest.mark.parametrize("hold_on", [False, True], ids=["flag_off", "flag_on"])
def test_resume_during_the_hold_carries_the_fragment(hold_on: bool) -> None:
    h = _hold_harness(hold_on, resume_after_s=0.2)

    async def _script() -> None:
        await h.turn("I want to check")
        await h.turn("I want to check", "last month's traffic")

    h.run(_script)
    spoken = "".join(call.args[0] for call in h.service._push_llm_text.await_args_list)
    if hold_on:
        assert len(h.calls) == 2
        assert h.calls[1]["query"] == "I want to check last month's traffic"
        assert spoken.count("Sure, what should I check?") == 1, "the fragment itself is never answered"
        assert len(h.persisted) == 1
    else:
        assert h.calls[1]["query"] != "I want to check last month's traffic"
        assert spoken.count("Sure, what should I check?") == 2


def test_hold_releases_at_the_window_end_without_a_resume() -> None:
    h = _hold_harness(True, resume_after_s=None)

    async def _script() -> None:
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        await h.turn("I want to check")
        return loop.time() - t0

    elapsed: list[float] = []

    async def _timed() -> None:
        elapsed.append(await _script())

    h.run(_timed)
    assert len(h.calls) == 1
    assert "Sure, what should I check?" in "".join(c.args[0] for c in h.service._push_llm_text.await_args_list)
    assert 0.55 <= elapsed[0] < 1.5, "held once, for the window"


def test_complete_finals_are_not_held() -> None:
    h = _hold_harness(True, resume_after_s=None)

    async def _timed() -> None:
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        await h.turn("show me last month's traffic")
        assert loop.time() - t0 < 0.3

    h.run(_timed)
    assert len(h.calls) == 1
