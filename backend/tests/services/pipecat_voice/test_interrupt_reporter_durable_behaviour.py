"""Behavioural coverage for barge-in durability in ElevenLabsInterruptReporter.

Runs the real reporter, the real ``_persist_conversation_turn`` and the real
audit/stop helpers against ``FakeSupabase``, which honours ``eq`` filters,
primary keys and atomic batch inserts. Replaces the old filter-ignoring mocks
and the source-text ``index()`` checks.
"""
from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from typing import Any

import pytest
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseStartFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.routers.assistant import _persist_conversation_turn
from app.services import chat_turn_cancel_service
from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter
from tests.support.fake_supabase import FakeQuery, FakeSupabase

ORG = "00000000-0000-4000-8000-0000000000a1"
OTHER_ORG = "00000000-0000-4000-8000-0000000000b2"
USER = "00000000-0000-4000-8000-0000000000c3"
ASSISTANT_ID = "00000000-0000-4000-8000-0000000000d4"
SETTINGS = SimpleNamespace()

HEARD = "The rollout starts Monday with the pilot team."
FULL = HEARD + " Then we expand to every region by the end of the month."


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    client = FakeSupabase()
    monkeypatch.setattr("app.workflows.repository.get_supabase_client", lambda _s: client)
    monkeypatch.setattr("app.routers.assistant.get_supabase_client", lambda _s: client)
    # In-process stop flags instead of Redis.
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    chat_turn_cancel_service._local_stops.clear()
    return client


async def _reporter(**kwargs: Any) -> tuple[ElevenLabsInterruptReporter, list[Frame]]:
    reporter = ElevenLabsInterruptReporter(
        reconcile_played_audio_enabled=True,
        settings=SETTINGS,
        org_id=ORG,
        user_id=USER,
        **kwargs,
    )
    await BaseObject.setup(reporter, TaskManager())
    pushed: list[Frame] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        pushed.append(frame)

    reporter.push_frame = _capture  # type: ignore[method-assign]
    return reporter, pushed


async def _speak_then_interrupt(reporter: ElevenLabsInterruptReporter, *, heard: str, full: str) -> None:
    class _Ledger:
        ever_recorded = True

        def snapshot(self) -> str:
            return heard

        def reset(self) -> None:
            pass

    reporter._spoken_ledger = _Ledger()
    await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await reporter.process_frame(
        OutputTransportMessageUrgentFrame(message={"type": "assistant_text", "delta": full}),
        FrameDirection.DOWNSTREAM,
    )
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)


def _completion_writer(conversation_id: str | None, user_text: str) -> tuple[str | None, str | None]:
    """What GravitreCognitiveLLMService does when the turn's stream completes."""
    return _persist_conversation_turn(
        SETTINGS,
        org_id=ORG,
        user_id=USER,
        conversation_id=conversation_id,
        user_text=user_text,
        assistant_text=FULL,
        tool_results=[],
        assistant_message_id=ASSISTANT_ID,
    )


@pytest.mark.asyncio
async def test_stop_frame_is_pushed_before_any_database_or_stop_write(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    reporter, pushed = await _reporter(conversation_id=conv)
    reporter.begin_turn("Walk me through the rollout plan")
    reporter.mark_turn_persisted(conversation_id=conv, assistant_message_id=None)

    loop_thread = threading.get_ident()
    writes: list[tuple[str, str, bool, bool]] = []

    def _record(query: FakeQuery) -> None:
        stop_pushed = any(isinstance(f, InterruptionFrame) for f in pushed)
        writes.append((query.op, query.table, stop_pushed, threading.get_ident() == loop_thread))

    db.hooks.append(_record)
    await _speak_then_interrupt(reporter, heard=HEARD, full=FULL)
    # Nothing has touched the database yet: process_frame returned as soon as
    # the stop frame was pushed.
    assert writes == []
    assert isinstance(pushed[-1], InterruptionFrame)

    await reporter.settle_barge_in()
    await reporter.flush_bookkeeping()
    assert writes, "barge-in bookkeeping never ran"
    assert all(stop_pushed for _, _, stop_pushed, _ in writes)
    assert not any(on_loop for _, _, _, on_loop in writes), "a barge-in write ran on the event loop"
    actions = {row["action"] for row in db.rows("audit_events")}
    assert "voice.barge_in.write_gate" in actions
    assert "voice.barge_in.reconciled" in actions


@pytest.mark.asyncio
async def test_completed_row_is_rewritten_to_the_heard_prefix(db: FakeSupabase) -> None:
    """Probe C: the completion committed before the interrupt."""
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    _completion_writer(conv, "Walk me through the rollout plan")
    reporter, _ = await _reporter(conversation_id=conv)
    reporter.begin_turn("Walk me through the rollout plan")
    reporter.mark_turn_persisted(conversation_id=conv, assistant_message_id=ASSISTANT_ID)

    await _speak_then_interrupt(reporter, heard=HEARD, full=FULL)
    await reporter.settle_barge_in()
    await reporter.flush_bookkeeping()

    assistant = db.rows("conversation_messages", role="assistant")
    assert [row["content"] for row in assistant] == [HEARD]
    assert len(db.rows("conversation_messages", role="user")) == 1


@pytest.mark.asyncio
async def test_interrupt_before_completion_commits_keeps_one_heard_turn(db: FakeSupabase) -> None:
    """Probe A: the reporter commits first, then the completion insert loses on the primary key."""
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    reporter, _ = await _reporter(conversation_id=conv)
    reporter.begin_turn("Walk me through the rollout plan")
    reporter.mark_turn_persisted(conversation_id=conv, assistant_message_id=ASSISTANT_ID)

    await _speak_then_interrupt(reporter, heard=HEARD, full=FULL)
    await reporter.settle_barge_in()
    await reporter.flush_bookkeeping()
    assert _completion_writer(conv, "Walk me through the rollout plan") == (None, None)

    assistant = db.rows("conversation_messages", role="assistant")
    assert [(row["id"], row["content"]) for row in assistant] == [(ASSISTANT_ID, HEARD)]
    assert len(db.rows("conversation_messages", role="user")) == 1


@pytest.mark.asyncio
async def test_completion_landing_between_update_and_insert_still_ends_heard(db: FakeSupabase) -> None:
    """Probe B: the completion commits after the reporter's update missed but before its insert."""
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    reporter, _ = await _reporter(conversation_id=conv)
    reporter.begin_turn("Walk me through the rollout plan")
    reporter.mark_turn_persisted(conversation_id=conv, assistant_message_id=ASSISTANT_ID)

    fired = {"done": False}

    def _race(query: FakeQuery) -> None:
        if query.op == "insert" and query.table == "conversation_messages" and not fired["done"]:
            fired["done"] = True
            db.hooks.remove(_race)
            _completion_writer(conv, "Walk me through the rollout plan")

    db.hooks.append(_race)
    await _speak_then_interrupt(reporter, heard=HEARD, full=FULL)
    await reporter.settle_barge_in()
    await reporter.flush_bookkeeping()

    assert fired["done"]
    assistant = db.rows("conversation_messages", role="assistant")
    assert [(row["id"], row["content"]) for row in assistant] == [(ASSISTANT_ID, HEARD)]
    assert len(db.rows("conversation_messages", role="user")) == 1


@pytest.mark.asyncio
async def test_previous_turn_answer_is_never_rewritten(db: FakeSupabase) -> None:
    """Mid-generation interrupt: no row for this turn yet, an older answer exists."""
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    _persist_conversation_turn(
        SETTINGS, org_id=ORG, user_id=USER, conversation_id=conv,
        user_text="What's our budget?", assistant_text="Twelve thousand.", tool_results=[],
    )
    reporter, _ = await _reporter(conversation_id=conv)
    reporter.begin_turn("Walk me through the rollout plan")

    await _speak_then_interrupt(reporter, heard=HEARD, full=FULL)
    await reporter.settle_barge_in()
    await reporter.flush_bookkeeping()

    contents = sorted(row["content"] for row in db.rows("conversation_messages", role="assistant"))
    assert contents == sorted(["Twelve thousand.", HEARD])


@pytest.mark.asyncio
async def test_foreign_conversation_rows_are_untouched(db: FakeSupabase) -> None:
    foreign = db.seed_conversation(org_id=OTHER_ORG, user_id=USER)
    db.tables.setdefault("conversation_messages", []).append(
        {"id": ASSISTANT_ID, "conversation_id": foreign, "role": "assistant", "content": FULL}
    )
    reporter, _ = await _reporter(conversation_id=foreign)
    reporter.begin_turn("Walk me through the rollout plan")
    reporter.mark_turn_persisted(conversation_id=foreign, assistant_message_id=ASSISTANT_ID)

    await _speak_then_interrupt(reporter, heard=HEARD, full=FULL)
    await reporter.settle_barge_in()
    await reporter.flush_bookkeeping()

    assert db.rows("conversation_messages", conversation_id=foreign)[0]["content"] == FULL


@pytest.mark.asyncio
async def test_heard_prefix_stays_with_the_interrupted_turn_when_next_turn_starts_first(db: FakeSupabase) -> None:
    """The next user turn can begin before the detached write runs."""
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    reporter, _ = await _reporter(conversation_id=conv)
    reporter.begin_turn("Walk me through the rollout plan")

    await _speak_then_interrupt(reporter, heard=HEARD, full=FULL)
    reporter.begin_turn("Actually, just the pilot part")
    await reporter.settle_barge_in()
    await reporter.flush_bookkeeping()

    users = [row["content"] for row in db.rows("conversation_messages", role="user")]
    assert users == ["Walk me through the rollout plan"]
    assert [row["content"] for row in db.rows("conversation_messages", role="assistant")] == [HEARD]


@pytest.mark.asyncio
async def test_barge_in_stop_is_released_for_the_next_turn(db: FakeSupabase) -> None:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    reporter, _ = await _reporter(conversation_id=conv)
    reporter.begin_turn("Walk me through the rollout plan")
    await _speak_then_interrupt(reporter, heard=HEARD, full=FULL)

    # The detached bookkeeping arms the stop for the interrupted turn...
    while reporter._post_interrupt_tasks:
        await asyncio.sleep(0.01)
    assert chat_turn_cancel_service.is_stop_requested(ORG, conv, settings=SETTINGS)

    # ...and the next confirmed turn releases it instead of being skipped.
    await reporter.settle_barge_in()
    await reporter.flush_bookkeeping()
    assert not chat_turn_cancel_service.is_stop_requested(ORG, conv, settings=SETTINGS)


# --- Bookkeeping stays off the next turn's critical path (audit finding 5) ----


@pytest.mark.asyncio
async def test_next_turn_does_not_wait_for_the_durable_rewrite(db: FakeSupabase) -> None:
    """A slow history write (or the playback report wait) no longer holds the
    next turn back; only the shared stop marker write is waited for, then the
    marker is released. The rewrite still lands before the next turn's rows."""
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    reporter, _ = await _reporter(conversation_id=conv)
    reporter.begin_turn("Walk me through the rollout plan")
    release = threading.Event()

    def _slow_history(query: FakeQuery) -> None:
        if query.table == "conversation_messages" and query.op in {"insert", "update"}:
            assert release.wait(5)

    db.hooks.append(_slow_history)
    await _speak_then_interrupt(reporter, heard=HEARD, full=FULL)

    await asyncio.wait_for(reporter.settle_barge_in(), timeout=1.0)
    assert chat_turn_cancel_service.is_stop_requested(ORG, conv) is False, "the next turn is not refused"
    assert reporter._post_interrupt_tasks, "the rewrite is still running"

    release.set()
    await asyncio.wait_for(reporter.flush_bookkeeping(), timeout=5.0)
    assert [r["content"] for r in db.rows("conversation_messages", role="assistant")] == [HEARD]


@pytest.mark.asyncio
async def test_marker_release_waits_for_the_shared_stop_write(db: FakeSupabase, monkeypatch: pytest.MonkeyPatch) -> None:
    """Released before the shared write lands, the late write would re-arm
    the marker and the next turn would answer nothing."""
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    reporter, _ = await _reporter(conversation_id=conv)
    reporter.begin_turn("Walk me through the rollout plan")
    release = threading.Event()
    real = reporter._arm_shared_stop_sync

    def _slow_shared(turn: Any) -> bool:
        assert release.wait(5)
        return real(turn)

    monkeypatch.setattr(reporter, "_arm_shared_stop_sync", _slow_shared)
    await _speak_then_interrupt(reporter, heard=HEARD, full=FULL)
    settle = asyncio.create_task(reporter.settle_barge_in())
    await asyncio.sleep(0.05)
    assert not settle.done()
    release.set()
    await asyncio.wait_for(settle, timeout=5.0)
    assert chat_turn_cancel_service.is_stop_requested(ORG, conv) is False
    await reporter.flush_bookkeeping()
