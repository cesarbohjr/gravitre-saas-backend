"""After a barge-in, history keeps only answer text that was heard.

Runs the real reporter, tap and tracker against ``FakeSupabase``. Covers:
* filler / tool narration never stored as the answer (on by default);
* ``voice_playback_grounded_history_v1`` on: cut at the browser's played
  position and marked; no report -> server estimate, still marked;
* flag off: no wait, no marker.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    OutputTransportMessageUrgentFrame,
    TTSAudioRawFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.routers.assistant import _persist_conversation_turn
from app.services import chat_turn_cancel_service
from app.services.pipecat_voice import voice_reply_playback
from app.services.pipecat_voice.interrupt_reporter import (
    ElevenLabsInterruptReporter,
    _HeardContext,
    resolve_heard_answer,
)
from app.services.pipecat_voice.spoken_text_tap import SpokenTextLedger, SpokenTextTapProcessor
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from app.services.pipecat_voice.voice_reply_playback import (
    ANSWER,
    FILLER,
    NOTHING_HEARD_MARKER,
    PROGRESS,
    TRUNCATION_MARKER,
    UNCONFIRMED_MARKER,
    ReplyPlayback,
    VoicePlaybackTracker,
)
from tests.support.fake_supabase import FakeSupabase

ORG = "00000000-0000-4000-8000-0000000000a1"
USER = "00000000-0000-4000-8000-0000000000c3"
ASSISTANT_ID = "00000000-0000-4000-8000-0000000000d4"
SETTINGS = SimpleNamespace()
RATE = 24000

FILLER_TEXT = "Sure, let me look. "
PROGRESS_TEXT = "Let me check your CRM. "
ANSWER_TEXT = "Revenue was up twelve percent this quarter. Churn fell to two percent."
SPOKEN = "Sure, let me look. Let me check your CRM. Revenue was up twelve percent this quarter.".split()


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


async def _setup(conv: str, *, grounded: bool) -> dict[str, Any]:
    session = VoicePipelineSession()
    session.begin_reply()
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: session.reply_id)
    ledger = SpokenTextLedger()
    reporter = ElevenLabsInterruptReporter(
        reconcile_played_audio_enabled=True,
        settings=SETTINGS,
        org_id=ORG,
        user_id=USER,
        conversation_id=conv,
        spoken_ledger=ledger,
        voice_session=session,
        playback_tracker=tracker,
        playback_grounded_history_enabled=grounded,
    )
    await BaseObject.setup(reporter, TaskManager())
    pushed: list[Frame] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        pushed.append(frame)

    reporter.push_frame = _capture  # type: ignore[method-assign]
    tap = SpokenTextTapProcessor(ledger, playback=tracker)
    await BaseObject.setup(tap, TaskManager())
    tap.push_frame = _noop  # type: ignore[method-assign]
    return {"session": session, "tracker": tracker, "reporter": reporter, "tap": tap, "pushed": pushed}


async def _speak(env: dict[str, Any], *, words: list[str], ms_per_word: float = 200.0) -> None:
    reporter = env["reporter"]
    await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    for delta, kind in ((FILLER_TEXT, FILLER), (PROGRESS_TEXT, PROGRESS), (ANSWER_TEXT, ANSWER)):
        await reporter.process_frame(
            OutputTransportMessageUrgentFrame(message={"type": "assistant_text", "delta": delta, "kind": kind}),
            FrameDirection.DOWNSTREAM,
        )
    for word in words:
        await env["tap"].process_frame(TTSTextFrame(text=word, aggregated_by="word"), FrameDirection.DOWNSTREAM)
        frames = int(RATE * ms_per_word / 1000)
        await env["tap"].process_frame(TTSAudioRawFrame(b"\x00\x00" * frames, RATE, 1), FrameDirection.DOWNSTREAM)


async def _finish(reporter: ElevenLabsInterruptReporter) -> None:
    for _ in range(300):
        if not reporter._post_interrupt_tasks:
            return
        await asyncio.sleep(0.01)


def _interrupted_payload(pushed: list[Frame]) -> dict[str, Any]:
    return next(
        f.message
        for f in pushed
        if isinstance(f, OutputTransportMessageUrgentFrame) and f.message.get("type") == "speech.interrupted"
    )


def _completed_row(db: FakeSupabase, conv: str) -> None:
    _persist_conversation_turn(
        SETTINGS,
        org_id=ORG,
        user_id=USER,
        conversation_id=conv,
        user_text="How did revenue do?",
        assistant_text=ANSWER_TEXT,
        tool_results=[],
        assistant_message_id=ASSISTANT_ID,
    )


@pytest.mark.asyncio
async def test_filler_and_narration_are_not_stored_as_the_answer_by_default(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    env = await _setup(conv, grounded=False)
    reporter = env["reporter"]
    reporter.begin_turn("How did revenue do?")
    # The whole spoken prefix including filler and narration was heard.
    await _speak(env, words=SPOKEN)
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    await _finish(reporter)

    payload = _interrupted_payload(env["pushed"])
    # The client still sees exactly what was said...
    assert payload["reconciled_text"].startswith("Sure, let me look. Let me check your CRM. Revenue")
    # ...but the answer part is what history keeps.
    assert payload["reconciled_answer_text"] == "Revenue was up twelve percent this quarter."
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    assert stored == ["Revenue was up twelve percent this quarter."]


@pytest.mark.asyncio
async def test_interrupted_during_filler_stores_no_answer_text(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    env = await _setup(conv, grounded=False)
    reporter = env["reporter"]
    reporter.begin_turn("How did revenue do?")
    await _speak(env, words=["Sure,", "let", "me"])
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    await _finish(reporter)
    # Nothing of the answer was heard: no assistant row is invented for it.
    assert db.rows("conversation_messages", role="assistant") == []


@pytest.mark.asyncio
async def test_grounded_history_cuts_at_the_browser_played_position_and_marks_it(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    _completed_row(db, conv)
    env = await _setup(conv, grounded=True)
    reporter = env["reporter"]
    rewrites: list[tuple[str, str]] = []
    reporter.on_assistant_rewritten = lambda mid, text: rewrites.append((mid, text))
    reporter.begin_turn("How did revenue do?")
    reporter.mark_turn_persisted(conversation_id=conv, assistant_message_id=ASSISTANT_ID)
    await _speak(env, words=SPOKEN)
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    # The server-side estimate is the whole spoken prefix; the browser had
    # only played through "was" (words start every 200 ms; "was" is word 10,
    # 2000-2200 ms; a word counts once all of it has played).
    env["tracker"].note_client_report(
        {"type": "playback.progress", "reply_id": env["session"].reply_id, "played_ms": 2250, "interrupted": True}
    )
    await _finish(reporter)

    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    assert stored == [f"Revenue was {TRUNCATION_MARKER}"]
    assert rewrites == [(ASSISTANT_ID, f"Revenue was {TRUNCATION_MARKER}")]


@pytest.mark.asyncio
async def test_grounded_history_without_a_report_is_marked_unconfirmed(
    db: FakeSupabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(voice_reply_playback, "CLIENT_REPORT_WAIT_S", 0.01)
    monkeypatch.setattr(
        VoicePlaybackTracker,
        "wait_for_client_report",
        lambda self, rid, timeout_s=0.01: asyncio.sleep(0.01, result=None),
    )
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    env = await _setup(conv, grounded=True)
    reporter = env["reporter"]
    reporter.begin_turn("How did revenue do?")
    await _speak(env, words=SPOKEN)
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    await _finish(reporter)

    # Sent is not heard: kept, but never presented to the model as heard.
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    assert stored == [f"Revenue was up twelve percent this quarter. {UNCONFIRMED_MARKER}"]


@pytest.mark.asyncio
async def test_flag_off_never_waits_for_or_uses_a_client_report(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    env = await _setup(conv, grounded=False)
    reporter = env["reporter"]

    async def _must_not_wait(*_a: Any, **_k: Any) -> None:
        raise AssertionError("flag off must not wait for the browser")

    env["tracker"].wait_for_client_report = _must_not_wait  # type: ignore[method-assign]
    reporter.begin_turn("How did revenue do?")
    await _speak(env, words=SPOKEN)
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    env["tracker"].note_client_report(
        {"reply_id": env["session"].reply_id, "played_ms": 300, "interrupted": True}
    )
    await _finish(reporter)
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    assert stored == ["Revenue was up twelve percent this quarter."]
    assert TRUNCATION_MARKER not in stored[0]


def _ctx(reply: ReplyPlayback | None, offset: int | None, server_text: str, generating: bool = False) -> _HeardContext:
    return _HeardContext(
        reply=reply, reply_id=1, server_offset=offset, server_text=server_text, still_generating=generating
    )


def test_resolve_heard_answer_variants():
    reply = ReplyPlayback(reply_id=1)
    reply.add_text("One moment. ", FILLER)
    reply.add_text("The deal closed on Friday. It was the largest this year.", ANSWER)
    cut = reply.draft.index(" It was")
    text, meta = resolve_heard_answer(_ctx(reply, cut, reply.draft[:cut]))
    assert text == "The deal closed on Friday."
    assert meta["answer_truncated"] is True
    assert meta["non_answer_chars_dropped"] == len("One moment. ")
    # Grounded: marked.
    text, _ = resolve_heard_answer(_ctx(reply, len(reply.draft), reply.draft), offset=cut, grounded=True)
    assert text == f"The deal closed on Friday. {TRUNCATION_MARKER}"
    # Grounded, nothing of the answer heard.
    text, _ = resolve_heard_answer(_ctx(reply, 3, "One"), offset=3, grounded=True)
    assert text == NOTHING_HEARD_MARKER
    # Whole answer heard and generation finished: no marker even when grounded.
    text, meta = resolve_heard_answer(_ctx(reply, len(reply.draft), reply.draft), grounded=True)
    assert text == "The deal closed on Friday. It was the largest this year."
    assert meta["answer_truncated"] is False
    # Whole draft heard but the brain was still generating: the rest was never heard.
    text, _ = resolve_heard_answer(_ctx(reply, len(reply.draft), reply.draft, generating=True), grounded=True)
    assert text.endswith(TRUNCATION_MARKER)


def test_resolve_heard_answer_keeps_legacy_text_without_labels():
    # Answer-only reply: exactly the reconciled text, as before.
    reply = ReplyPlayback(reply_id=1)
    reply.add_text("The sync finished. Three records were skipped.", ANSWER)
    text, meta = resolve_heard_answer(_ctx(reply, 19, "The sync finished."))
    assert text == "The sync finished."
    assert meta["heard_text_basis"] == "server_text"
    # No reply at all (draft from LLM frames only).
    text, _ = resolve_heard_answer(_ctx(None, None, "The sync finished."))
    assert text == "The sync finished."


# ---- socket dropped mid-reply (voice_playback_grounded_history_v1) ----------


async def _completed_turn(env: dict[str, Any], db: FakeSupabase, conv: str, *, words: list[str]) -> None:
    reporter = env["reporter"]
    reporter.begin_turn("How did revenue do?")
    await _speak(env, words=words)
    await reporter.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
    _completed_row(db, conv)
    reporter.mark_turn_persisted(conversation_id=conv, assistant_message_id=ASSISTANT_ID)


@pytest.mark.asyncio
async def test_drop_mid_reply_rewrites_the_stored_reply_to_what_was_heard(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    env = await _setup(conv, grounded=True)
    await _completed_turn(env, db, conv, words=SPOKEN)
    # The last periodic report: played through "was" (2000-2200 ms).
    env["tracker"].note_client_report(
        {"type": "playback.progress", "reply_id": env["session"].reply_id, "played_ms": 2300}
    )
    meta = await env["reporter"].reconcile_on_disconnect()
    await _finish(env["reporter"])

    assert meta is not None and meta["action"] == "rewritten" and meta["heard_source"] == "client_playback"
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    assert stored == [f"Revenue was {TRUNCATION_MARKER}"]


@pytest.mark.asyncio
async def test_drop_without_a_report_is_marked_unconfirmed(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    env = await _setup(conv, grounded=True)
    await _completed_turn(env, db, conv, words=SPOKEN)
    meta = await env["reporter"].reconcile_on_disconnect()
    await _finish(env["reporter"])

    assert meta is not None and meta["heard_source"] == "unknown" and meta["exposure"] == "unknown"
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    # Audio through "quarter." was sent; whether it played is unknown.
    assert stored == [f"Revenue was up twelve percent this quarter. {UNCONFIRMED_MARKER}"]


@pytest.mark.asyncio
async def test_drop_after_a_full_reply_with_no_report_is_marked_unconfirmed(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    env = await _setup(conv, grounded=True)
    words = (FILLER_TEXT + PROGRESS_TEXT + ANSWER_TEXT).split()
    await _completed_turn(env, db, conv, words=words)
    meta = await env["reporter"].reconcile_on_disconnect()
    await _finish(env["reporter"])

    assert meta is not None and meta["action"] == "rewritten"
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    assert stored == [f"{ANSWER_TEXT} {UNCONFIRMED_MARKER}"]


@pytest.mark.asyncio
async def test_drop_after_the_reply_was_heard_in_full_changes_nothing(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    env = await _setup(conv, grounded=True)
    words = (FILLER_TEXT + PROGRESS_TEXT + ANSWER_TEXT).split()
    await _completed_turn(env, db, conv, words=words)
    reply = env["tracker"].reply(env["session"].reply_id, create=False)
    # The browser's last cumulative report: all of it played.
    env["tracker"].note_client_report(
        {"type": "playback.progress", "reply_id": env["session"].reply_id, "played_ms": reply.sent_audio_ms}
    )
    meta = await env["reporter"].reconcile_on_disconnect()
    await _finish(env["reporter"])

    assert meta is not None and meta["action"] == "heard_in_full"
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    assert stored == [ANSWER_TEXT]


@pytest.mark.asyncio
async def test_drop_while_still_generating_cuts_the_row_once_it_is_stored(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    env = await _setup(conv, grounded=True)
    reporter = env["reporter"]
    reporter.begin_turn("How did revenue do?")
    await _speak(env, words=SPOKEN[:12])  # through "up"
    meta = await reporter.reconcile_on_disconnect()
    assert meta is not None and meta["action"] == "pending_until_persisted"
    assert db.rows("conversation_messages", role="assistant") == []
    # The completion writer stores the full reply afterwards...
    _completed_row(db, conv)
    reporter.mark_turn_persisted(conversation_id=conv, assistant_message_id=ASSISTANT_ID)
    await _finish(reporter)
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    # ...and it is cut to what was sent ("up" was still arriving), with no
    # report: marked as not known to be heard.
    assert stored == [f"Revenue was {UNCONFIRMED_MARKER}"]


@pytest.mark.asyncio
async def test_drop_with_the_flag_off_leaves_the_stored_reply_alone(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    env = await _setup(conv, grounded=False)
    await _completed_turn(env, db, conv, words=SPOKEN)
    assert await env["reporter"].reconcile_on_disconnect() is None
    await _finish(env["reporter"])
    stored = [row["content"] for row in db.rows("conversation_messages", role="assistant")]
    assert stored == [ANSWER_TEXT]
