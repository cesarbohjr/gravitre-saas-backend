"""Spoken formatting and abbreviation-aware sentence cuts for TTS.

Table-driven checks of ``spoken_formatting`` (what the voice says for a
displayed amount, date, time, id or address, and where a streamed answer is
cut into sentences), then the same behaviour through the live bridge
(``GravitreCognitiveLLMService``) and through barge-in accounting: a reply
with an amount and a date cut part-way stores the displayed text that was
heard, never the spoken rewrite and never a half-heard amount.
"""
from __future__ import annotations



import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseStartFrame,
    OutputTransportMessageUrgentFrame,
    TTSAudioRawFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services import chat_turn_cancel_service
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter
from app.services.pipecat_voice.llm_context_utils import (
    merge_durable_and_socket_history,
)
from app.services.pipecat_voice.spoken_formatting import (
    format_for_speech,
    spoken_alignment_tokens,
    to_spoken_form,
)
from app.services.pipecat_voice.spoken_text_tap import (
    SpokenTextLedger,
    SpokenTextTapProcessor,
)
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from app.services.pipecat_voice.voice_conversational_polish import (
    reconcile_played_audio,
)
from app.services.pipecat_voice.voice_reply_playback import (
    ANSWER,
    TRUNCATION_MARKER,
    ReplyPlayback,
    VoicePlaybackTracker,
)
from app.services.voice_session_service import split_speakable_chunks
from tests.support.fake_supabase import FakeSupabase

# Scripted brain events; provider policy/budget data is supplied by an explicit offline fixture.
pytestmark = pytest.mark.usefixtures("scripted_voice_external_sources")

# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

FORMAT_CASES: list[tuple[str, str]] = [
    # Currency: every digit kept, never rounded.
    ("The total is $1,250.50.", "The total is 1,250 dollars and 50 cents."),
    ("It costs $5 per seat.", "It costs 5 dollars per seat."),
    ("Only $1 today", "Only 1 dollar today"),
    ("$1,250.00 even", "1,250 dollars even"),
    ("$0.99 each", "99 cents each"),
    ("$1.05 each", "1 dollar and 5 cents each"),
    ("$1.5 each", "1 dollar and 50 cents each"),
    ("$0.125 per call", "0.125 dollars per call"),
    ("€3.99 or £1.01", "3 euros and 99 cents or 1 pound and 1 penny"),
    ("£20.50", "20 pounds and 50 pence"),
    ("a $2.5M budget", "a 2.5 million dollars budget"),
    ("a $3k fee", "a 3 thousand dollars fee"),
    ("a $5 million deal", "a 5 million dollars deal"),
    # Percentages and ranges.
    ("grew 12.5%", "grew 12.5 percent"),
    ("up 15 %", "up 15 percent"),
    ("10-15% growth", "10 to 15 percent growth"),
    ("pages 10-15", "pages 10 to 15"),
    ("$10-$15 range", "10 to 15 dollars range"),
    ("$10-15 range", "10 to 15 dollars range"),
    ("$10.50-$15 range", "10 dollars and 50 cents to 15 dollars range"),
    ("the 2024-2025 season", "the 2024 to 2025 season"),
    ("won 3-2", "won 3-2"),  # a score, not a range
    ("the 2024-25 season", "the 2024-25 season"),
    ("COVID-19 and GPT-4", "COVID-19 and GPT-4"),
    # Dates: ISO and unambiguous forms only.
    ("Due 2026-10-11.", "Due October 11th, 2026."),
    ("At 2026-10-11T14:30Z.", "At October 11th, 2026 at 2:30 PM UTC."),
    ("on Oct 11", "on October 11th"),
    ("on Oct 11, 2026", "on October 11th, 2026"),
    ("on Sept. 2", "on September 2nd"),
    ("on May 22", "on May 22nd"),
    ("on Feb 30", "on Feb 30"),  # not a date
    ("on 13/04/2026", "on April 13th, 2026"),
    ("on 04/13/2026", "on April 13th, 2026"),
    ("on 03/03/2026", "on March 3rd, 2026"),
    # Ambiguous: read literally, never converted to a guessed month.
    ("on 03/04/2026", "on zero three slash zero four slash 2026"),
    ("on 3/4/2026", "on 3 slash 4 slash 2026"),
    ("on 2026-13-40", "on 2026-13-40"),
    # Times.
    ("Meet at 14:30.", "Meet at 2:30 PM."),
    ("at 14:00", "at 2 PM"),
    ("at 00:15", "at 12:15 AM"),
    ("at 09:05", "at 9:05 AM"),
    ("at 9:05", "at 9:05"),  # morning or evening: as written
    ("at 9am", "at 9 AM"),
    ("at 9:30 p.m. tomorrow", "at 9:30 PM tomorrow"),
    ("at 9 a.m. Then", "at 9 AM. Then"),
    # Phone numbers, order / ticket ids and UUIDs.
    ("Call (555) 123-4567 now", "Call 5 5 5, 1 2 3, 4 5 6 7 now"),
    ("Call 1-800-555-1234.", "Call 1, 8 0 0, 5 5 5, 1 2 3 4."),
    ("Call +44 20 7946 0958.", "Call plus 4 4, 2 0, 7 9 4 6, 0 9 5 8."),
    ("Order ORD-12345 shipped", "Order O R D, 1 2 3, 4 5 shipped"),
    ("Invoice INV-2026-0042", "Invoice I N V, 2 0 2 6, 0 0 4 2"),
    ("ticket #4821", "ticket number 4 8 2 1"),
    ("ticket #48213", "ticket number 4 8 2, 1 3"),
    ("Record 3f2a9c1e-1b2c-4d5e-8f90-a1b2c3d4e5f6 saved.", "Record ID ending in E 5 F 6 saved."),
    ("id: 3f2a9c1e-1b2c-4d5e-8f90-a1b2c3d4e5f6", "ID ending in E 5 F 6"),
    ("run 9f86d081884c7d659a2feaa0c55ad015", "run ID ending in D 0 1 5"),
    # E-mail addresses and URLs (domain only).
    ("Email bob.smith@example.com today.", "Email bob dot smith at example dot com today."),
    ("See https://www.example.com/pricing?x=1.", "See example dot com."),
    ("See http://docs.acme.io:8080/a/b, then", "See docs dot acme dot io, then"),
    ("Visit gravitre.com/pricing.", "Visit gravitre dot com."),
    # Left alone.
    ("version 2.1.3 shipped", "version 2.1.3 shipped"),
    ("rated 3.5 stars", "rated 3.5 stars"),
    ("We have 1,250 users.", "We have 1,250 users."),
    ("Nothing to change here.", "Nothing to change here."),
    ("", ""),
]


@pytest.mark.parametrize(("written", "spoken"), FORMAT_CASES)
def test_format_for_speech(written: str, spoken: str) -> None:
    assert format_for_speech(written) == spoken


@pytest.mark.parametrize(("written", "spoken"), FORMAT_CASES)
def test_formatting_is_idempotent(written: str, spoken: str) -> None:
    # Spoken text compared against stored text (history merge) is formatted
    # again: a second pass must not change it.
    assert format_for_speech(spoken) == spoken


def test_to_spoken_form_applies_aliases_after_formatting() -> None:
    assert to_spoken_form("e.g. $5 vs. $6") == "for example 5 dollars versus 6 dollars"
    assert to_spoken_form("Gravitre costs $5", '{"Gravitre": "Grav eetray"}') == "Grav eetray costs 5 dollars"


def test_a_full_uuid_is_never_read() -> None:
    uuid = "3f2a9c1e-1b2c-4d5e-8f90-a1b2c3d4e5f6"
    spoken = format_for_speech(f"Your record {uuid} is ready.")
    assert uuid not in spoken
    assert "3f2a" not in spoken and "1b2c" not in spoken


# ---------------------------------------------------------------------------
# Sentence chunker
# ---------------------------------------------------------------------------

CHUNK_CASES: list[tuple[str, list[str], str]] = [
    # (buffer, ready sentences, remainder)
    ("Sure. ", ["Sure."], ""),
    ("Sure.", ["Sure."], ""),  # first-chunk fast path: no wait for the next delta
    ("Done! Next", ["Done!"], "Next"),
    ("Really? Yes", ["Really?"], "Yes"),
    ("We use e.g. apples. Then", ["We use e.g. apples."], "Then"),
    ("That is i.e. the plan. Ok", ["That is i.e. the plan."], "Ok"),
    ("Dr. Smith is in. Ok", ["Dr. Smith is in."], "Ok"),
    ("Mr. and Ms. Lee came. Ok", ["Mr. and Ms. Lee came."], "Ok"),
    ("The U.S. market grew. Then", ["The U.S. market grew."], "Then"),
    ("It is approx. 5 miles. Ok", ["It is approx. 5 miles."], "Ok"),
    ("Apples vs. pears. Ok", ["Apples vs. pears."], "Ok"),
    ("Apples, pears, etc. and more. Ok", ["Apples, pears, etc. and more."], "Ok"),
    ("Apples, pears, etc. Then more", ["Apples, pears, etc."], "Then more"),
    ("Call J. R. Smith now. Ok", ["Call J. R. Smith now."], "Ok"),
    ("Room No. 5 is free. Ok", ["Room No. 5 is free."], "Ok"),
    ("No. I can't. Ok", ["No.", "I can't."], "Ok"),
    ("It costs 3.5 dollars. Ok", ["It costs 3.5 dollars."], "Ok"),
    ("Meet at 10.30 tomorrow. Ok", ["Meet at 10.30 tomorrow."], "Ok"),
    ("Version 2.1.3 shipped. Ok", ["Version 2.1.3 shipped."], "Ok"),
    ("Visit example.com today. Ok", ["Visit example.com today."], "Ok"),
    ("Mail bob@acme.com today. Ok", ["Mail bob@acme.com today."], "Ok"),
    ("Go to https://acme.com/a.b today. Ok", ["Go to https://acme.com/a.b today."], "Ok"),
    # A period that may still continue waits for the next delta.
    ("It costs 3.", [], "It costs 3."),
    ("Meet at 10.", [], "Meet at 10."),
    ("Mail bob@acme.", [], "Mail bob@acme."),
    ("Visit acme.com.", [], "Visit acme.com."),
    ("We use e.g.", [], "We use e.g."),
    ("Ask Dr. ", [], "Ask Dr. "),
    ("The U.S. ", [], "The U.S. "),
    ("Call J.", [], "Call J."),
]


@pytest.mark.parametrize(("buffer", "ready", "rest"), CHUNK_CASES)
def test_split_speakable_chunks_respects_abbreviations(buffer: str, ready: list[str], rest: str) -> None:
    assert split_speakable_chunks(buffer) == (ready, rest)


def test_streamed_decimal_is_not_cut_at_its_point() -> None:
    chunks, buffer = [], ""
    for delta in ["The total is $1,250", ".", "50 today", ". Next"]:
        ready, buffer = split_speakable_chunks(buffer + delta)
        chunks.extend(ready)
    assert chunks == ["The total is $1,250.50 today."]
    assert buffer == "Next"


def test_long_unpunctuated_buffer_still_gets_the_emergency_split() -> None:
    buffer = "word " * 60
    ready, _rest = split_speakable_chunks(buffer, min_chars=12)
    assert ready and len(ready[0]) < len(buffer)


# ---------------------------------------------------------------------------
# Alignment of spoken words to the displayed draft
# ---------------------------------------------------------------------------


def test_alignment_tokens_tie_a_rewrite_to_its_displayed_span() -> None:
    draft = "Total $1,250.50 due 2026-10-11."
    tokens = spoken_alignment_tokens(draft)
    words = [w for w, _ in tokens]
    assert words == [
        "total", "1", "250", "dollars", "and", "50", "cents", "due", "october", "11th", "2026",
    ]
    amount_start, amount_end = draft.index("$"), draft.index(" due")
    # Every word of the amount but the last points before it: only the whole
    # amount counts as heard.
    assert [end for _, end in tokens[1:6]] == [amount_start] * 5
    assert tokens[6][1] == amount_end
    assert tokens[-1][1] == draft.index(".", amount_end + 5)


@pytest.mark.parametrize(
    ("spoken", "reconciled"),
    [
        ("Your total is 1,250 dollars", "Your total is"),
        ("Your total is 1,250 dollars and 50 cents, due", "Your total is $1,250.50, due"),
        ("Your total is 1,250 dollars and 50 cents, due October 11th,", "Your total is $1,250.50, due"),
        (
            "Your total is 1,250 dollars and 50 cents, due October 11th, 2026.",
            "Your total is $1,250.50, due 2026-10-11.",
        ),
    ],
)
def test_reconcile_maps_spoken_rewrites_back_to_the_displayed_text(spoken: str, reconciled: str) -> None:
    draft = "Your total is $1,250.50, due 2026-10-11. Shall I pay it?"
    result = reconcile_played_audio(spoken_text=spoken, full_draft_text=draft)
    assert result.reconciled_text == reconciled
    assert result.truncated


def test_history_merge_matches_spoken_socket_text_to_the_stored_displayed_row() -> None:
    durable = [
        {"role": "user", "content": "What do I owe?", "_live": True},
        {"role": "assistant", "content": "You owe $1,250.50 by 2026-10-11.", "_live": True},
    ]
    socket = [
        {"role": "user", "content": "What do I owe?"},
        {"role": "assistant", "content": "You owe 1,250 dollars and 50 cents by October 11th, 2026."},
        {"role": "user", "content": "Pay it."},
    ]
    merged = merge_durable_and_socket_history(durable, socket)
    # The spoken copy is recognised as the stored row: not repeated, and the
    # model keeps the displayed form.
    assert [m["content"] for m in merged] == [
        "What do I owe?",
        "You owe $1,250.50 by 2026-10-11.",
        "Pay it.",
    ]


# ---------------------------------------------------------------------------
# Through the live bridge
# ---------------------------------------------------------------------------


def _drive(deltas: list[str]) -> tuple[list[str], list[str]]:
    """Run one turn of the real bridge; return (client deltas, TTS-bound text)."""

    async def _fake_stream(**_kwargs: Any):
        for d in deltas:
            yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": d})
        yield AssistantStreamComplete(full_content="".join(deltas), tool_results=[], react_result=None, model="test")

    fake_intelligence = type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(_fake_stream)})()
    service = GravitreCognitiveLLMService(
        app_settings=object(),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
    )
    display: list[str] = []
    tts: list[str] = []

    async def _capture_push_frame(frame: Any, *_a: Any, **_kw: Any) -> None:
        message = getattr(frame, "message", None)
        if isinstance(message, dict) and message.get("type") == "assistant_text":
            display.append(str(message.get("delta") or ""))

    async def _capture_tts(text: str) -> None:
        tts.append(text)

    service.push_frame = AsyncMock(side_effect=_capture_push_frame)
    service._push_llm_text = AsyncMock(side_effect=_capture_tts)

    class _Context:
        def get_messages(self) -> list[dict[str, Any]]:
            return [{"role": "user", "content": "What do I owe?"}]

    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=fake_intelligence):
        asyncio.run(service._run_gravitre_turn(_Context()))
    return display, tts


def test_bridge_speaks_formatted_sentences_and_displays_the_text_unchanged() -> None:
    deltas = [
        "Your total is $1,250",
        ".",
        "50, due on 2026-10-11",
        ". ",
        "Dr",
        ". ",
        "Smith signs",
        " it, e.g. ",
        "today. ",
        "Call 555-123-4567.",
    ]
    display, tts = _drive(deltas)
    # The client shows exactly what the model wrote.
    assert "".join(display).strip() == "".join(deltas).strip()
    # TTS gets whole sentences in spoken form; no cut after "$1,250.",
    # "Dr." or "e.g.".
    assert [t.strip() for t in tts] == [
        "Your total is 1,250 dollars and 50 cents, due on October 11th, 2026.",
        "Dr. Smith signs it, for example today.",
        "Call 5 5 5, 1 2 3, 4 5 6 7.",
    ]


# ---------------------------------------------------------------------------
# Barge-in: the heard prefix is stored in displayed form
# ---------------------------------------------------------------------------

ORG = "00000000-0000-4000-8000-0000000000a1"
USER = "00000000-0000-4000-8000-0000000000c3"
RATE = 24000
ANSWER_TEXT = "Your total is $1,250.50, due 2026-10-11. Shall I pay it now?"


def _spoken_words() -> list[str]:
    # What ElevenLabs times, word by word, for the spoken copy of ANSWER_TEXT.
    return to_spoken_form(ANSWER_TEXT).split()


def test_tracker_heard_prefix_never_splits_an_amount_or_a_date() -> None:
    reply = ReplyPlayback(reply_id=1)
    reply.add_text(ANSWER_TEXT, ANSWER)
    words = _spoken_words()
    assert words[:8] == ["Your", "total", "is", "1,250", "dollars", "and", "50", "cents,"]
    for word in words:
        reply.note_spoken_word(word, 0.0)
        reply.note_audio(int(RATE * 0.2) * 2, RATE)  # 200 ms per word

    def heard(ms: float) -> str:
        return reply.answer_text_upto(reply.char_offset_for_played_ms(ms)[0])

    # "dollars" (word 4) played, "cents," (word 7) not yet: the amount is not heard.
    assert heard(1000) == "Your total is"
    # Through "cents,": the whole amount, in displayed form.
    assert heard(1600) == "Your total is $1,250.50,"
    # Through "October 11th," but not "2026.": the date is not heard.
    assert heard(2200) == "Your total is $1,250.50, due"
    assert heard(2400) == "Your total is $1,250.50, due 2026-10-11."


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    client = FakeSupabase()
    monkeypatch.setattr("app.workflows.repository.get_supabase_client", lambda _s: client)
    monkeypatch.setattr("app.routers.assistant.get_supabase_client", lambda _s: client)
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    chat_turn_cancel_service._local_stops.clear()
    return client


async def _noop(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
    return None


async def _interrupt_after(conv: str, words: list[str], *, grounded: bool, played_ms: float | None = None) -> None:
    session = VoicePipelineSession()
    session.begin_reply()
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: session.reply_id)
    ledger = SpokenTextLedger()
    reporter = ElevenLabsInterruptReporter(
        reconcile_played_audio_enabled=True,
        settings=object(),
        org_id=ORG,
        user_id=USER,
        conversation_id=conv,
        spoken_ledger=ledger,
        voice_session=session,
        playback_tracker=tracker,
        playback_grounded_history_enabled=grounded,
    )
    await BaseObject.setup(reporter, TaskManager())
    reporter.push_frame = _noop  # type: ignore[method-assign]
    tap = SpokenTextTapProcessor(ledger, playback=tracker)
    await BaseObject.setup(tap, TaskManager())
    tap.push_frame = _noop  # type: ignore[method-assign]

    reporter.begin_turn("What do I owe?")
    await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await reporter.process_frame(
        OutputTransportMessageUrgentFrame(message={"type": "assistant_text", "delta": ANSWER_TEXT, "kind": ANSWER}),
        FrameDirection.DOWNSTREAM,
    )
    for word in words:
        await tap.process_frame(TTSTextFrame(text=word, aggregated_by="word"), FrameDirection.DOWNSTREAM)
        frames = int(RATE * 0.2)
        await tap.process_frame(TTSAudioRawFrame(b"\x00\x00" * frames, RATE, 1), FrameDirection.DOWNSTREAM)
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    if played_ms is not None:
        tracker.note_client_report(
            {"type": "playback.progress", "reply_id": session.reply_id, "played_ms": played_ms, "interrupted": True}
        )
    for _ in range(300):
        if not reporter._post_interrupt_tasks:
            break
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_interrupted_reply_with_an_amount_and_a_date_stores_the_displayed_heard_prefix(
    db: FakeSupabase,
) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    words = _spoken_words()
    # Cut after "October 11th,": the amount was heard, the date was not.
    cut = words.index("11th,") + 1
    await _interrupt_after(conv, words[:cut], grounded=False)
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    assert stored == ["Your total is $1,250.50, due"]


@pytest.mark.asyncio
async def test_grounded_history_maps_the_browser_played_position_through_the_spoken_rewrite(
    db: FakeSupabase,
) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    words = _spoken_words()
    # Everything up to "Shall" was sent; the browser played through "cents,"
    # (8 words of 200 ms).
    await _interrupt_after(conv, words[: words.index("Shall")], grounded=True, played_ms=1600)
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    assert stored == [f"Your total is $1,250.50, {TRUNCATION_MARKER}"]
