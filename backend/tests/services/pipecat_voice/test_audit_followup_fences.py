"""Follow-up to the PR #351 review (2026-10-10): three gaps it reproduced.

1. A failed task_state read must never count as known state. The state
   service swallowed read errors and returned the default state, so the
   strict adoption check saw "known, empty" and could adopt.
2. A background replay must not overwrite a correction. An adopted run's
   deferred task_state write, replayed after its turn was cancelled and the
   user saved a correction, replaced the correction.
3. The retained-size budget must not undercount. A payload nested deeper
   than the walker went, or held in an unrecognised object, counted as zero.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.conversation_state_service import ConversationStateService
from app.services.pipecat_voice.speculative_generation import (
    SpeculativeGenerationCoordinator,
    _retained_size,
    compute_revision_versions,
    load_revision_task_state,
    start_speculative_run,
)
from app.services.speculative_execution import SpeculativeScope, speculative_scope
from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation
from tests.services.fake_supabase_db import FakeSupabaseDB

ORG = "11111111-1111-4111-8111-111111111111"
USER = "22222222-2222-4222-8222-222222222222"
CONV = "33333333-3333-4333-8333-333333333333"
SETTINGS = SimpleNamespace(
    supabase_url="https://test.supabase.co",
    supabase_anon_key="anon-test",
    supabase_service_role_key="service-role-test",
)


class _FailingDB:
    """Every query fails the way a dropped connection does."""

    def table(self, _name: str) -> Any:
        return self

    def __getattr__(self, _name: str) -> Any:
        return lambda *_a, **_k: self

    def execute(self) -> Any:
        raise ConnectionError("db unavailable")


def _seeded_db() -> FakeSupabaseDB:
    db = FakeSupabaseDB()
    db.tables["conversations"] = [{"id": CONV, "org_id": ORG, "user_id": USER, "task_state": {}}]
    return db


def _plan(db: FakeSupabaseDB) -> Any:
    return db.tables["conversations"][0]["task_state"].get("current_plan")


# ---------------------------------------------------------------------------
# 1. A failed state read is unknown, inside the real state service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_failed_state_read_is_unknown_not_default() -> None:
    with patch("app.services.conversation_state_service.get_supabase_client", lambda _s=None: _FailingDB()):
        service = ConversationStateService(SETTINGS)
        # Callers that want the old fail-open default still get it.
        assert (await service.get_task_state(CONV, ORG))["pending_task"] is None
        with pytest.raises(ConnectionError):
            await service.get_task_state(CONV, ORG, strict=True)
        state = await load_revision_task_state(SETTINGS, org_id=ORG, conversation_id=CONV)
    assert state == {"_unavailable": True}
    versions = compute_revision_versions(
        conversation_id=CONV, task_state=state, history=[], history_summary=None
    )
    assert versions.known is False


@pytest.mark.asyncio
async def test_failed_reads_on_both_sides_never_adopt() -> None:
    with patch("app.services.conversation_state_service.get_supabase_client", lambda _s=None: _FailingDB()):
        run_state = await load_revision_task_state(SETTINGS, org_id=ORG, conversation_id=CONV)
        turn_state = await load_revision_task_state(SETTINGS, org_id=ORG, conversation_id=CONV)

    def _versions(state: Any) -> Any:
        return compute_revision_versions(conversation_id=CONV, task_state=state, history=[], history_summary=None)

    coordinator = SpeculativeGenerationCoordinator()
    revision = coordinator.note_transcript("what is two plus two")

    async def _answer():
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Four."})

    run = start_speculative_run(
        text="what is two plus two", runner=_answer, create_task=asyncio.ensure_future, revision=revision
    )
    run.versions = _versions(run_state)
    coordinator.set_run(run)
    await run.task
    assert coordinator.adopt("what is two plus two", strict=True, versions=_versions(turn_state)) is None
    assert coordinator.last_reject_reason == "versions_unknown"


# ---------------------------------------------------------------------------
# 2. A late replay never overwrites a correction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_delayed_replay_cannot_overwrite_a_corrected_task() -> None:
    db = _seeded_db()
    service = ConversationStateService(SETTINGS)
    old_turn = TurnCancellation()
    scope = SpeculativeScope()

    # The speculative run (old turn) decides an objective; the write is deferred.
    with bound_turn_cancellation(old_turn), speculative_scope(scope):
        await service.update_task_state(CONV, ORG, {"current_plan": {"objective": "email the team"}}, client=db)
    assert _plan(db) is None, "deferred, not written"

    # Adopted, but the replay is held back.
    assert scope.begin_commit()
    # The user cancels the old turn and saves a correction.
    old_turn.cancel("held_correction")
    new_turn = TurnCancellation()
    with bound_turn_cancellation(new_turn):
        await service.update_task_state(CONV, ORG, {"current_plan": {"objective": "email only Dana"}}, client=db)
    assert _plan(db) == {"objective": "email only Dana"}

    # The replay is released, from a context with no turn bound at all.
    await scope.replay()
    assert _plan(db) == {"objective": "email only Dana"}, "the old objective must not replace the correction"


@pytest.mark.asyncio
async def test_a_replay_from_a_live_turn_still_lands() -> None:
    db = _seeded_db()
    service = ConversationStateService(SETTINGS)
    turn = TurnCancellation()
    scope = SpeculativeScope()
    with bound_turn_cancellation(turn), speculative_scope(scope):
        await service.update_task_state(CONV, ORG, {"current_plan": {"objective": "email the team"}}, client=db)
    assert scope.begin_commit()
    await scope.replay()
    assert _plan(db) == {"objective": "email the team"}


@pytest.mark.asyncio
async def test_a_cancelled_turn_cannot_write_task_state_directly() -> None:
    db = _seeded_db()
    service = ConversationStateService(SETTINGS)
    turn = TurnCancellation()
    turn.cancel("barge_in")
    with bound_turn_cancellation(turn):
        await service.update_task_state(CONV, ORG, {"current_plan": {"objective": "stale"}}, client=db)
    assert _plan(db) is None


@pytest.mark.asyncio
async def test_a_late_write_after_the_replay_keeps_its_turn_fence() -> None:
    db = _seeded_db()
    service = ConversationStateService(SETTINGS)
    turn = TurnCancellation()
    scope = SpeculativeScope()
    assert scope.begin_commit()
    await scope.replay()
    turn.cancel("held_task_cancel")
    # A write that reaches the scope after its replay finished runs on the
    # late-write thread, which has no context of its own: the fence travels
    # with the write.
    with bound_turn_cancellation(turn):
        scope.defer(
            "conversation.task_state",
            lambda: service._persist_state(CONV, ORG, {"current_plan": {"objective": "stale"}}, client=db),
        )
    await scope.wait_flushed()
    assert _plan(db) is None


# ---------------------------------------------------------------------------
# 3. The retained-size budget never undercounts
# ---------------------------------------------------------------------------


def _nested(depth: int, leaf: Any) -> Any:
    value = leaf
    for _ in range(depth):
        value = {"k": value}
    return value


def test_a_deeply_nested_payload_counts_as_over_budget() -> None:
    deep = _nested(40, "x" * 1_000_000)
    assert _retained_size(deep, 512_000) > 512_000


def test_a_large_payload_inside_an_object_is_counted() -> None:
    holder = SimpleNamespace(rows=["y" * 1000] * 600)
    assert _retained_size({"output": holder}) >= 600_000


def test_shallow_small_payloads_stay_small() -> None:
    assert _retained_size({"delta": "Four.", "n": 3, "ok": True}) < 2_000


@pytest.mark.asyncio
async def test_a_deep_tool_payload_discards_the_run() -> None:
    tool = AssistantStreamEvent(
        sse_type="tool-output-available",
        payload={"toolCallId": "c1", "output": _nested(40, "z" * 3_000_000)},
    )
    done = AssistantStreamComplete(full_content="ok", tool_results=[], react_result=None, model="t")

    async def _run():
        yield tool
        yield done

    run = start_speculative_run(text="pull every deal", runner=_run, create_task=asyncio.ensure_future)
    await run.task
    assert run.outcome == "over_budget"


# ---------------------------------------------------------------------------
# Full audit (2026-10-10), step 1
# ---------------------------------------------------------------------------


class _SlowDB(FakeSupabaseDB):
    """Every query takes 150 ms of blocking I/O, like a slow database."""

    def table(self, name: str) -> Any:
        query = super().table(name)
        execute = query.execute

        def _slow_execute() -> Any:
            time.sleep(0.15)
            return execute()

        query.execute = _slow_execute
        return query


@pytest.mark.asyncio
async def test_slow_state_persistence_never_blocks_the_event_loop() -> None:
    """F1: two 150 ms database calls used to delay a 10 ms timer to ~300 ms."""
    db = _SlowDB()
    db.tables["conversations"] = [{"id": CONV, "org_id": ORG, "user_id": USER, "task_state": {}}]
    service = ConversationStateService(SETTINGS)
    loop = asyncio.get_running_loop()
    started = loop.time()
    fired: list[float] = []
    timer = asyncio.ensure_future(asyncio.sleep(0.01))
    timer.add_done_callback(lambda _t: fired.append(loop.time() - started))
    write = asyncio.ensure_future(
        service.update_task_state(CONV, ORG, {"current_plan": {"objective": "email the team"}}, client=db)
    )
    await asyncio.gather(timer, write)
    assert fired[0] < 0.1, f"an independent 10 ms timer fired after {fired[0] * 1000:.0f} ms"
    assert _plan(db) == {"objective": "email the team"}


@pytest.mark.asyncio
async def test_concurrent_writers_do_not_lose_updates() -> None:
    """Off the loop, the read-merge-write of one conversation is still serial."""
    db = _SlowDB()
    db.tables["conversations"] = [{"id": CONV, "org_id": ORG, "user_id": USER, "task_state": {}}]
    service = ConversationStateService(SETTINGS)
    await asyncio.gather(
        service.update_task_state(CONV, ORG, {"rejected_options": ["a"]}, client=db),
        service.update_task_state(CONV, ORG, {"rejected_options": ["b"]}, client=db),
    )
    assert sorted(db.tables["conversations"][0]["task_state"]["rejected_options"]) == ["a", "b"]


def _memory_writes(db: FakeSupabaseDB) -> list[Any]:
    return [w for w in db.writes if w[1] == "agent_memories"]


async def _replay_memory_promotion(*, cancel_before_release: bool) -> FakeSupabaseDB:
    from app.services.workspace_memory_service import promote_turn_memories

    db = _seeded_db()
    db.tables["agents"] = [{"id": "44444444-4444-4444-8444-444444444444", "org_id": ORG}]
    origin = TurnCancellation()
    scope = SpeculativeScope()
    gate = asyncio.Event()

    async def _audit() -> None:
        await gate.wait()

    with bound_turn_cancellation(origin), speculative_scope(scope):
        scope.defer("audit.write_audit_event", _audit)
        promote_turn_memories(
            db,
            org_id=ORG,
            user_id=USER,
            conversation_id=CONV,
            settings=SETTINGS,
            memories=[{"category": "preference", "content": "Send updates to the whole team", "key": "updates"}],
        )
    assert _memory_writes(db) == [], "deferred, not written"
    assert scope.begin_commit()
    replay = asyncio.ensure_future(scope.replay())
    await asyncio.sleep(0)  # the replay is paused inside the audit write
    if cancel_before_release:
        origin.cancel("held_correction")
    gate.set()
    await replay
    return db


@pytest.mark.asyncio
async def test_a_cancelled_replay_does_not_promote_memory() -> None:
    """F2: replay paused, origin turn cancelled, replay released: no memory row."""
    db = await _replay_memory_promotion(cancel_before_release=True)
    assert _memory_writes(db) == []


@pytest.mark.asyncio
async def test_a_live_replay_still_promotes_memory() -> None:
    db = await _replay_memory_promotion(cancel_before_release=False)
    assert _memory_writes(db), "control: an uncancelled replay writes the memory"


@pytest.mark.asyncio
async def test_a_cancelled_turn_drops_its_channel_override_and_ledger_promotion() -> None:
    from app.services.turn_cancellation import superseded_write

    turn = TurnCancellation()
    with bound_turn_cancellation(turn):
        assert superseded_write("conversation.channel_override") is False
        turn.cancel("barge_in")
        assert superseded_write("conversation.channel_override") is True
    assert superseded_write("conversation.channel_override") is False, "no turn bound: nothing to fence"


def test_a_slotted_object_is_counted_through_its_slots() -> None:
    class _Slotted:
        __slots__ = ("payload",)

        def __init__(self, payload: str) -> None:
            self.payload = payload

    assert _retained_size(_Slotted("s" * 1_000_000)) >= 1_000_000


def test_wide_characters_count_their_real_size() -> None:
    text = "\U0001F600" * 200_000
    assert _retained_size(text) >= 800_000


def test_an_opaque_object_counts_as_over_budget() -> None:
    class _Opaque:
        __slots__ = ()

    import array

    assert _retained_size({"x": array.array("b", b"x" * 10)}, 512_000) > 512_000
    assert _retained_size(_Opaque(), 512_000) <= 512_000, "an empty slotted object is still visible"
