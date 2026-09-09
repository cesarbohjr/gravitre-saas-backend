"""Does ElevenLabsInterruptReporter ever observe TTS-aligned spoken text?

The reporter is placed at ``[... llm, interrupt_reporter, tts, transport.output(),
assistant_agg]`` in ``pipeline.py``. ``TTSTextFrame`` is created inside Pipecat's
``TTSService`` and pushed *downstream* (``push_frame`` with no direction), so it
travels tts -> transport.output() -> assistant_agg. It can never arrive at a
processor placed upstream of tts.

These tests pin the reporter's real observable behaviour so the Phase 5
reconciliation is judged against what actually reaches it in production, not
against a hand-fed frame sequence that the live topology cannot produce.
"""
from __future__ import annotations

import pytest
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    OutputTransportMessageUrgentFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.base_object import BaseObject
from pipecat.utils.asyncio.task_manager import TaskManager

from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter
from app.services.pipecat_voice.spoken_text_tap import (
    SpokenTextLedger,
    SpokenTextTapProcessor,
)


async def _noop_push(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
    return None


async def _drive(frames: list[Frame], **reporter_kwargs) -> list[dict]:
    """Feed frames to the reporter and return the speech.interrupted payloads.

    Same harness pattern as the sibling speculative-prefetch tests: a real
    TaskManager (InterruptionFrame handling needs one) plus a captured
    ``push_frame`` instead of standing up a full pipeline.
    """
    reporter = ElevenLabsInterruptReporter(**reporter_kwargs)
    await BaseObject.setup(reporter, TaskManager())

    pushed: list[Frame] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
        pushed.append(frame)

    reporter.push_frame = _capture  # type: ignore[method-assign]

    for frame in frames:
        await reporter.process_frame(frame, FrameDirection.DOWNSTREAM)

    return [
        f.message
        for f in pushed
        if isinstance(f, OutputTransportMessageUrgentFrame)
        and isinstance(f.message, dict)
        and f.message.get("type") == "speech.interrupted"
    ]


@pytest.mark.asyncio
async def test_without_a_ledger_the_reporter_degrades_safely_to_no_truncation():
    """REGRESSION (original defect): with only the frames the live pipeline
    delivers to this processor (LLM text — no TTSTextFrame, because tts is
    downstream), there is no spoken signal. The reporter must then assume the
    whole draft was heard and drop nothing. This is the safe degradation, and it
    is exactly why the feature was inert before SpokenTextTapProcessor existed.
    """
    payloads = await _drive(
        [
            LLMFullResponseStartFrame(),
            LLMTextFrame(text="The sync finished. "),
            LLMTextFrame(text="Three records were skipped."),
            InterruptionFrame(),
        ],
        reconcile_played_audio_enabled=True,
    )
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["reconcile_played_audio"] is True
    # spoken_text falls back to the full draft, so there is nothing to truncate.
    assert payload["spoken_text"] == payload["full_draft_text"]
    assert payload["match_strategy"] == "full_match"
    assert payload["dropped_chars"] == 0
    assert payload["truncated"] is False
    assert payload["spoken_source"] == "draft_fallback"


@pytest.mark.asyncio
async def test_tap_ledger_makes_reconciliation_actually_truncate():
    """THE FIX: the ledger the downstream tap fills is the spoken signal, so a
    barge-in genuinely drops the drafted tail the user never heard.
    """
    ledger = SpokenTextLedger()
    tap = SpokenTextTapProcessor(ledger)
    await BaseObject.setup(tap, TaskManager())
    tap.push_frame = _noop_push  # type: ignore[method-assign]

    # Playback progresses: the transport releases word-level TTS text downstream.
    for word in ("The", "sync", "finished."):
        await tap.process_frame(
            TTSTextFrame(text=word, aggregated_by="word"), FrameDirection.DOWNSTREAM
        )

    payloads = await _drive(
        [
            LLMTextFrame(text="The sync finished. "),
            LLMTextFrame(text="Three records were skipped."),
            InterruptionFrame(),
        ],
        reconcile_played_audio_enabled=True,
        spoken_ledger=ledger,
    )
    payload = payloads[0]
    assert payload["spoken_source"] == "tap_ledger"
    assert payload["reconciled_text"] == "The sync finished."
    assert payload["truncated"] is True
    assert payload["dropped_chars"] > 0


@pytest.mark.asyncio
async def test_empty_ledger_that_never_recorded_does_not_truncate_everything():
    """SAFETY: if the tap is unwired or broken it has never recorded anything, so
    an empty ledger must NOT be read as "nothing was heard" — that would wipe
    every assistant turn to the empty string, which is worse than reconciling
    nothing.
    """
    ledger = SpokenTextLedger()
    assert ledger.ever_recorded is False

    payloads = await _drive(
        [
            LLMTextFrame(text="The sync finished."),
            InterruptionFrame(),
        ],
        reconcile_played_audio_enabled=True,
        spoken_ledger=ledger,
    )
    payload = payloads[0]
    assert payload["spoken_source"] == "draft_fallback"
    assert payload["reconciled_text"] == "The sync finished."
    assert payload["truncated"] is False


@pytest.mark.asyncio
async def test_empty_ledger_after_proven_liveness_reports_nothing_spoken():
    """Once the tap has proven it works, an empty ledger is genuine silence —
    interrupted before any audio played, so nothing was heard.
    """
    ledger = SpokenTextLedger()
    ledger.append("earlier turn audio")
    ledger.reset()
    assert ledger.ever_recorded is True
    assert ledger.snapshot() == ""

    payloads = await _drive(
        [
            LLMTextFrame(text="Never heard this."),
            InterruptionFrame(),
        ],
        reconcile_played_audio_enabled=True,
        spoken_ledger=ledger,
    )
    payload = payloads[0]
    assert payload["spoken_source"] == "tap_ledger"
    assert payload["match_strategy"] == "nothing_spoken"
    assert payload["reconciled_text"] == ""
    assert payload["truncated"] is True


@pytest.mark.asyncio
async def test_reporter_resets_ledger_between_turns():
    ledger = SpokenTextLedger()
    ledger.append("stale text from the previous turn")
    await _drive([LLMFullResponseStartFrame()], spoken_ledger=ledger)
    assert ledger.snapshot() == ""
    assert ledger.ever_recorded is True


class TestSpokenTextLedger:
    def test_parts_join_with_spaces_so_words_do_not_run_together(self):
        ledger = SpokenTextLedger()
        for word in ("The", "sync", "finished."):
            ledger.append(word)
        assert ledger.snapshot() == "The sync finished."

    def test_blank_appends_are_ignored_and_do_not_set_liveness(self):
        ledger = SpokenTextLedger()
        ledger.append("")
        ledger.append("   ")
        assert ledger.ever_recorded is False
        assert ledger.snapshot() == ""

    def test_reset_clears_text_but_never_clears_liveness(self):
        ledger = SpokenTextLedger()
        ledger.append("spoken")
        ledger.reset()
        assert ledger.snapshot() == ""
        assert ledger.ever_recorded is True


@pytest.mark.asyncio
async def test_tap_passes_every_frame_through_unchanged():
    """The tap sits between transport.output() and assistant_agg, so dropping or
    mutating frames here would break assistant context accumulation.
    """
    ledger = SpokenTextLedger()
    tap = SpokenTextTapProcessor(ledger)
    await BaseObject.setup(tap, TaskManager())

    forwarded: list[Frame] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
        forwarded.append(frame)

    tap.push_frame = _capture  # type: ignore[method-assign]

    sent = [
        TTSTextFrame(text="spoken", aggregated_by="word"),
        LLMTextFrame(text="drafted"),
        LLMFullResponseStartFrame(),
    ]
    for frame in sent:
        await tap.process_frame(frame, FrameDirection.DOWNSTREAM)

    assert forwarded == sent


@pytest.mark.asyncio
async def test_alignment_logic_is_correct_when_tts_text_is_actually_present():
    """CONTRAST: the same reporter truncates correctly once TTSTextFrames do
    arrive. This isolates the defect to frame routing (pipeline placement), not
    to reconcile_played_audio() itself.
    """
    payloads = await _drive(
        [
            LLMFullResponseStartFrame(),
            LLMTextFrame(text="The sync finished. "),
            LLMTextFrame(text="Three records were skipped."),
            TTSTextFrame(text="The sync finished.", aggregated_by="sentence"),
            InterruptionFrame(),
        ],
        reconcile_played_audio_enabled=True,
    )
    payload = payloads[0]
    assert payload["reconciled_text"] == "The sync finished."
    assert payload["dropped_chars"] > 0
    assert payload["truncated"] is True


@pytest.mark.asyncio
async def test_flag_off_emits_no_reconcile_fields():
    payloads = await _drive(
        [
            LLMFullResponseStartFrame(),
            LLMTextFrame(text="Some drafted answer."),
            InterruptionFrame(),
        ],
        reconcile_played_audio_enabled=False,
    )
    payload = payloads[0]
    assert "reconcile_played_audio" not in payload
    assert "match_strategy" not in payload
