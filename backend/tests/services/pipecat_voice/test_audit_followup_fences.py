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
    assert _retained_size({"delta": "Four.", "n": 3, "ok": True}) < 100


@pytest.mark.asyncio
async def test_a_deep_tool_payload_discards_the_run() -> None:
    tool = AssistantStreamEvent(
        sse_type="tool-output-available",
        payload={"toolCallId": "c1", "output": _nested(40, "z" * 1_000_000)},
    )
    done = AssistantStreamComplete(full_content="ok", tool_results=[], react_result=None, model="t")

    async def _run():
        yield tool
        yield done

    run = start_speculative_run(text="pull every deal", runner=_run, create_task=asyncio.ensure_future)
    await run.task
    assert run.outcome == "over_budget"
