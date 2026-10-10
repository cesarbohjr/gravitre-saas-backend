"""Per-reply playback accounting: labelled segments, word timings, client reports."""
from __future__ import annotations

import asyncio
import json

import pytest
from pipecat.frames.frames import Frame, InterruptionFrame, TTSAudioRawFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services.pipecat_voice.playback_report_serializer import (
    PlaybackReportingSerializer,
    handle_playback_report,
)
from app.services.pipecat_voice.spoken_text_tap import SpokenTextLedger, SpokenTextTapProcessor
from app.services.pipecat_voice.voice_reply_playback import (
    ANSWER,
    FILLER,
    PROGRESS,
    ReplyPlayback,
    VoicePlaybackTracker,
    strip_non_answer_speech,
)

RATE = 24000


def _audio_ms(ms: float) -> TTSAudioRawFrame:
    frames = int(RATE * ms / 1000)
    return TTSAudioRawFrame(b"\x00\x00" * frames, RATE, 1)


def _reply_with_filler() -> ReplyPlayback:
    reply = ReplyPlayback(reply_id=1)
    reply.add_text("Sure, let me look. ", FILLER)
    reply.add_text("Let me check your CRM. ", PROGRESS)
    reply.add_text("Revenue was up twelve percent.", ANSWER)
    reply.add_text(" Churn fell to two percent.", ANSWER)
    return reply


def test_segments_merge_by_kind_and_answer_text_excludes_filler_and_progress():
    reply = _reply_with_filler()
    assert [s.kind for s in reply.segments] == [FILLER, PROGRESS, ANSWER]
    assert reply.has_non_answer()
    assert reply.answer_text_upto(None) == "Revenue was up twelve percent. Churn fell to two percent."
    cut = reply.draft.index("twelve")
    assert reply.answer_text_upto(cut) == "Revenue was up"
    # Cut inside the filler: no answer heard at all.
    assert reply.answer_text_upto(5) == ""
    assert reply.non_answer_texts() == ["Sure, let me look.", "Let me check your CRM."]


def test_unknown_kind_is_treated_as_answer():
    reply = ReplyPlayback(reply_id=1)
    reply.add_text("Hello there.", "something-else")
    assert reply.segments[0].kind == ANSWER


def test_spoken_words_align_to_the_draft_and_stamp_first_audio_per_kind():
    reply = _reply_with_filler()
    kinds_seen: list[list[str]] = []
    t = 0.0
    for word in "Sure, let me look. Let me check your CRM. Revenue was up".split():
        reply.note_audio(int(RATE * 0.25) * 2, RATE)
        t += 0.25
        kinds_seen.append(reply.note_spoken_word(word, t))
    assert kinds_seen[0] == [FILLER]
    assert kinds_seen[4] == [PROGRESS]
    assert kinds_seen[9] == [ANSWER]
    assert sum(1 for k in kinds_seen if k) == 3
    assert reply.first_audio_at[FILLER] < reply.first_audio_at[PROGRESS] < reply.first_audio_at[ANSWER]
    # Each word records how much audio had been sent when it passed the tap.
    assert reply.word_marks[0][0] == pytest.approx(250.0)


def test_played_ms_maps_to_heard_text_through_word_timings():
    reply = _reply_with_filler()
    for word in "Sure, let me look. Let me check your CRM. Revenue was up twelve percent.".split():
        reply.note_spoken_word(word, 0.0)
        reply.note_audio(int(RATE * 0.2) * 2, RATE)  # 200 ms per word
    # Words 0..9 started at 0, 200, ..., 1800 ms: "Revenue" is word 9 (1800 ms).
    offset, method = reply.char_offset_for_played_ms(1900)
    assert method == "word_timings"
    assert reply.answer_text_upto(offset) == "Revenue"
    offset, _ = reply.char_offset_for_played_ms(2250)
    assert reply.answer_text_upto(offset) == "Revenue was up"
    offset, _ = reply.char_offset_for_played_ms(100)
    assert reply.answer_text_upto(offset) == ""


def test_played_ms_without_word_timings_spreads_characters_over_sent_audio():
    reply = ReplyPlayback(reply_id=1)
    reply.add_text("abcd efgh ijkl mnop", ANSWER)
    reply.note_audio(int(RATE * 1.0) * 2, RATE)  # 1 s sent, no words timed
    offset, method = reply.char_offset_for_played_ms(500)
    assert method == "char_spread"
    # Half the characters, snapped to the end of the word it lands in.
    assert reply.draft[:offset] == "abcd efgh"
    assert reply.char_offset_for_played_ms(0)[0] == 0


def test_spoken_word_that_differs_from_the_draft_never_over_claims():
    reply = ReplyPlayback(reply_id=1)
    reply.add_text("It costs $5 per seat.", ANSWER)
    for word in ("It", "costs", "five", "dollars"):
        reply.note_spoken_word(word, 0.0)
    # "five dollars" did not align: heard stays at "It costs".
    assert reply.draft[: reply.word_marks[-1][1]] == "It costs"
    reply.note_spoken_word("per", 0.0)
    assert reply.draft[: reply.word_marks[-1][1]] == "It costs $5 per"


def test_strip_non_answer_speech_removes_only_spoken_filler_sentences():
    phrases = ["Sure, let me look.", "Let me check your CRM."]
    spoken = "Sure let me look. Let me check your CRM. Revenue was up twelve percent."
    assert strip_non_answer_speech(spoken, phrases) == "Revenue was up twelve percent."
    assert strip_non_answer_speech("Sure, let me look.", phrases) == ""
    untouched = "I can look into that for you."
    assert strip_non_answer_speech(untouched, phrases) == untouched
    assert strip_non_answer_speech(untouched, []) == untouched


@pytest.mark.asyncio
async def test_tracker_waits_for_the_interrupted_client_report():
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: 4)
    tracker.note_assistant_text("Revenue was up.", ANSWER)
    tracker.mark_interrupted(4)

    async def _report_later() -> None:
        await asyncio.sleep(0.02)
        tracker.note_client_report(
            {"type": "playback.progress", "reply_id": 4, "played_ms": 640, "received_ms": 900, "interrupted": True}
        )

    task = asyncio.create_task(_report_later())
    reply = await tracker.wait_for_client_report(4, timeout_s=1.0)
    await task
    assert reply is not None
    assert reply.client_played_ms == 640
    assert reply.client_received_ms == 900
    assert reply.interrupted and reply.client_interrupted


@pytest.mark.asyncio
async def test_tracker_returns_none_when_no_report_arrives():
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: 2)
    tracker.note_assistant_text("Hello.", ANSWER)
    # A periodic (not interrupted) report is not the cut position.
    tracker.note_client_report({"reply_id": 2, "played_ms": 100, "interrupted": False})
    assert await tracker.wait_for_client_report(2, timeout_s=0.01) is None
    assert await tracker.wait_for_client_report(99, timeout_s=0.01) is None


def test_tracker_ignores_malformed_reports_and_keeps_played_monotonic():
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: 1)
    tracker.note_assistant_text("Hi.", ANSWER)
    assert tracker.note_client_report({"reply_id": "1", "played_ms": 10}) is False
    assert tracker.note_client_report({"reply_id": True, "played_ms": 10}) is False
    assert tracker.note_client_report({"reply_id": 1, "played_ms": -5}) is False
    assert tracker.note_client_report({"reply_id": 1, "played_ms": "nan"}) is False
    assert tracker.note_client_report({"reply_id": 1, "played_ms": 300}) is True
    assert tracker.note_client_report({"reply_id": 1, "played_ms": 200}) is True
    assert tracker.reply(1, create=False).client_played_ms == 300


def test_audio_and_words_follow_the_reply_stamped_on_the_frame_not_the_current_reply():
    from app.services.pipecat_voice.json_audio_serializer import REPLY_ID_ATTR
    from app.services.pipecat_voice.voice_reply_playback import AUDIO_REPLY_ID_ATTR

    assert AUDIO_REPLY_ID_ATTR == REPLY_ID_ATTR
    rid = {"value": 1}
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: rid["value"])
    tracker.note_assistant_text("Revenue was up.", ANSWER)
    rid["value"] = 2  # the next reply is already generating
    tracker.note_assistant_text("Next answer.", ANSWER)
    frame = _audio_ms(500)
    setattr(frame, REPLY_ID_ATTR, 1)  # still reply 1's audio being played out
    tracker.note_audio_frame(frame)
    tracker.note_spoken_word("Revenue")
    one = tracker.reply(1, create=False)
    two = tracker.reply(2, create=False)
    assert one.sent_audio_ms == pytest.approx(500)
    assert two.sent_audio_ms == 0
    assert one.word_marks and not two.word_marks


def test_unstamped_audio_falls_back_to_the_current_reply():
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: 3)
    tracker.note_assistant_text("Hi.", ANSWER)
    tracker.note_audio_frame(_audio_ms(100))
    assert tracker.reply(3, create=False).sent_audio_ms == pytest.approx(100)


def test_tracker_keeps_a_bounded_number_of_replies():
    rid = {"value": 0}
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: rid["value"])
    for n in range(1, 20):
        rid["value"] = n
        tracker.note_assistant_text("x", ANSWER)
    assert tracker.reply(1, create=False) is None
    assert tracker.reply(19, create=False) is not None


def test_playback_report_handler_routes_reports_and_passes_everything_else():
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: 3)
    tracker.note_assistant_text("Hi.", ANSWER)
    report = json.dumps({"type": "playback.progress", "reply_id": 3, "played_ms": 120})
    assert handle_playback_report(report, tracker) is True
    assert tracker.reply(3, create=False).client_played_ms == 120
    assert handle_playback_report(json.dumps({"type": "interrupt"}), tracker) is False
    assert handle_playback_report(b"\xff\xfe", tracker) is False
    # A broken report is consumed, never turned into a frame or an error.
    assert handle_playback_report('{"type": "playback.progress", "reply_id": ', tracker) is False


@pytest.mark.asyncio
async def test_reporting_serializer_consumes_reports_and_keeps_other_messages():
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: 1)
    tracker.note_assistant_text("Hi.", ANSWER)
    ser = PlaybackReportingSerializer(playback_tracker=tracker)
    frame = await ser.deserialize(
        json.dumps({"type": "playback.progress", "reply_id": 1, "played_ms": 50, "interrupted": True})
    )
    assert frame is None
    assert tracker.reply(1, create=False).client_interrupted is True
    interrupt = await ser.deserialize(json.dumps({"type": "interrupt"}))
    assert isinstance(interrupt, InterruptionFrame)


@pytest.mark.asyncio
async def test_tap_feeds_sent_audio_and_word_timings_to_the_tracker():
    first: list[tuple[str, int | None]] = []
    tracker = VoicePlaybackTracker(
        reply_id_getter=lambda: 5, on_first_audio=lambda kind, at, rid: first.append((kind, rid))
    )
    tracker.note_assistant_text("One moment. ", FILLER)
    tracker.note_assistant_text("It is sunny.", ANSWER)
    ledger = SpokenTextLedger()
    tap = SpokenTextTapProcessor(ledger, playback=tracker)
    await BaseObject.setup(tap, TaskManager())

    async def _noop(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        return None

    tap.push_frame = _noop  # type: ignore[method-assign]
    for word in ("One", "moment.", "It", "is", "sunny."):
        await tap.process_frame(TTSTextFrame(text=word, aggregated_by="word"), FrameDirection.DOWNSTREAM)
        await tap.process_frame(_audio_ms(100), FrameDirection.DOWNSTREAM)

    reply = tracker.reply(5, create=False)
    assert reply.sent_audio_ms == pytest.approx(500.0)
    assert ledger.snapshot() == "One moment. It is sunny."
    assert first == [(FILLER, 5), (ANSWER, 5)]
    assert tracker.last_audio_activity is not None
    assert tracker.non_answer_phrases() == ["One moment."]
