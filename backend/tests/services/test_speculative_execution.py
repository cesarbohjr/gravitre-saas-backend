"""The speculative (dry-run) scope every durable writer checks.

Unit-level proof per writer; the end-to-end proof through the real brain is
test_speculative_brain_side_effects.py.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.speculative_execution import (
    SpeculativeScope,
    SpeculativeSideEffectBlocked,
    block_if_speculative,
    current_scope,
    run_or_defer,
    speculative_scope,
)
from tests.services.fake_supabase_db import FakeSupabaseDB

ORG = "11111111-1111-4111-8111-111111111111"
USER = "22222222-2222-4222-8222-222222222222"
CONV = "33333333-3333-4333-8333-333333333333"


def _db() -> FakeSupabaseDB:
    db = FakeSupabaseDB()
    db.tables["conversations"] = [{"id": CONV, "org_id": ORG, "user_id": USER, "task_state": {}}]
    return db


def _state_service():
    from app.services.conversation_state_service import ConversationStateService

    return ConversationStateService(settings=SimpleNamespace())


async def _in_scope(scope: SpeculativeScope, coro_fn):
    """Run ``coro_fn()`` as its own task inside ``scope`` (like a speculative run)."""

    async def _body():
        with speculative_scope(scope):
            return await coro_fn()

    return await asyncio.create_task(_body())


class TestConversationTaskState:
    @pytest.mark.asyncio
    async def test_speculative_update_is_deferred_but_readable_by_the_run(self):
        db, svc, scope = _db(), _state_service(), SpeculativeScope()

        async def _run():
            await svc.update_task_state(CONV, ORG, {"active_objective": {"goal": "x"}}, client=db)
            return await svc.get_task_state(CONV, ORG, client=db)

        seen = await _in_scope(scope, _run)
        assert seen["active_objective"] == {"goal": "x"}  # read-your-writes inside the run
        assert db.writes == []
        assert db.tables["conversations"][0]["task_state"] == {}
        assert scope.deferred_labels == ["conversation.task_state"]

    @pytest.mark.asyncio
    async def test_discard_drops_and_commit_replays_through_the_same_merge(self):
        baseline_db, svc = _db(), _state_service()
        await svc.update_task_state(CONV, ORG, {"rejected_options": ["a"]}, client=baseline_db)
        await svc.update_task_state(CONV, ORG, {"rejected_options": ["b"]}, client=baseline_db)

        async def _run(db):
            await svc.update_task_state(CONV, ORG, {"rejected_options": ["a"]}, client=db)
            await svc.update_task_state(CONV, ORG, {"rejected_options": ["b"]}, client=db)

        dropped_db, dropped = _db(), SpeculativeScope()
        await _in_scope(dropped, lambda: _run(dropped_db))
        assert dropped.discard() == 2
        assert dropped_db.writes == []

        adopted_db, adopted = _db(), SpeculativeScope()
        await _in_scope(adopted, lambda: _run(adopted_db))
        assert await adopted.commit() == 2
        assert adopted_db.tables == baseline_db.tables

    @pytest.mark.asyncio
    async def test_consuming_an_approval_is_refused_and_blocks_the_run(self):
        db, svc, scope = _db(), _state_service(), SpeculativeScope()

        async def _run():
            return await svc.compare_and_set_pending_status(
                CONV, ORG, expected_status="awaiting_confirm", updates={}, client=db
            )

        with pytest.raises(SpeculativeSideEffectBlocked):
            await _in_scope(scope, _run)
        assert scope.blocked
        assert db.writes == []
        with pytest.raises(SpeculativeSideEffectBlocked):
            await scope.commit()

    @pytest.mark.asyncio
    async def test_conversation_row_creation_is_deferred(self):
        db, svc, scope = FakeSupabaseDB(), _state_service(), SpeculativeScope()

        async def _run():
            return await svc.ensure_owned_conversation(
                org_id=ORG, user_id=USER, conversation_id=CONV, client=db
            )

        with patch("app.services.conversation_state_service.assert_conversation_create_allowed"):
            assert await _in_scope(scope, _run) == CONV
            assert db.writes == []
            await scope.commit()
        assert [w[:2] for w in db.writes] == [("insert", "conversations")]


class TestKernelAndMemoryWriters:
    @pytest.mark.asyncio
    async def test_kernel_objective_trace_and_learn_are_deferred(self):
        from app.services.cognitive_turn_kernel import (
            CognitiveTurnContext,
            CognitiveTurnKernel,
            CognitiveTurnRequest,
        )

        db, scope = _db(), SpeculativeScope()
        kernel = CognitiveTurnKernel(settings=SimpleNamespace())
        request = CognitiveTurnRequest(org_id=ORG, message="hi", conversation_id=CONV, client=db, user_id=USER)
        ctx = CognitiveTurnContext(turn_id="t1")

        async def _run():
            with patch(
                "app.services.conversation_state_service.get_conversation_state_service",
                return_value=_state_service(),
            ):
                await kernel._persist_active_objective(request, {"goal": "g"})
                await kernel._persist_trace(request, ctx)
                return await kernel.run_learn(request, ctx, act_result={"confirmed": True})

        out = await _in_scope(scope, _run)
        assert out.learn.get("deferred") == "speculative"
        assert db.writes == []
        assert scope.deferred_labels == ["kernel.active_objective", "kernel.turn_trace", "kernel.learn"]
        scope.discard()
        assert db.writes == []

    @pytest.mark.asyncio
    async def test_memory_promotion_and_audit_rows_are_deferred(self):
        from app.services.workspace_memory_service import promote_turn_memories
        from app.workflows.audit import write_audit_event

        db, scope = _db(), SpeculativeScope()

        async def _run():
            written = promote_turn_memories(
                db, org_id=ORG, memories=[{"content": "likes blue", "category": "preference"}]
            )
            write_audit_event(db, ORG, USER, "x.y", "conversation", CONV, {})
            return written

        assert await _in_scope(scope, _run) == []
        assert db.writes == []
        assert scope.deferred_labels == ["memory.promote_turn_memories", "audit.write_audit_event"]

    @pytest.mark.asyncio
    async def test_audit_written_off_loop_still_sees_the_scope(self):
        from app.workflows.audit import _OFF_LOOP_WRITES, submit_audit_off_loop, write_audit_event

        db, scope = _db(), SpeculativeScope()

        async def _run():
            submit_audit_off_loop(write_audit_event, db, ORG, USER, "x.y", "conversation", CONV, {})
            await asyncio.gather(*list(_OFF_LOOP_WRITES))

        await _in_scope(scope, _run)
        assert db.writes == []
        assert scope.deferred_labels == ["audit.write_audit_event"]


class TestRefusedSideEffects:
    @pytest.mark.asyncio
    async def test_connector_write_invoke_is_refused_reads_are_not(self):
        from app.services.tool_types import ToolValidationError
        from app.services.voice_barge_in_write import raise_if_speculative_blocks_invoke

        scope = SpeculativeScope()

        async def _run():
            with patch(
                "app.services.voice_barge_in_write.action_is_mutating_write",
                side_effect=lambda action: action == "hubspot.contact.update",
            ):
                raise_if_speculative_blocks_invoke("hubspot.contact.list")  # READ: allowed
                assert not scope.blocked
                raise_if_speculative_blocks_invoke("hubspot.contact.update")

        with pytest.raises(ToolValidationError):
            await _in_scope(scope, _run)
        assert scope.blocked and "hubspot.contact.update" in (scope.blocked_reason or "")

    def test_invoke_tool_checks_the_speculative_gate_before_executing(self):
        from app.services.tool_service import invoke_tool

        class _Stop(Exception):
            pass

        ctx = SimpleNamespace(org_id=ORG, conversation_id=CONV, settings=None, client=None)
        with (
            patch("app.services.voice_barge_in_write.raise_if_speculative_blocks_invoke", side_effect=_Stop),
            patch("app.services.capability_availability.is_capability_action", return_value=False),
        ):
            with pytest.raises(_Stop):
                invoke_tool(ctx, "anything.read")

    @pytest.mark.asyncio
    async def test_staging_a_write_approval_is_refused(self):
        from app.services.react_write_gate import materialize_react_write_approval_turn

        scope = SpeculativeScope()

        async def _run():
            with patch(
                "app.services.react_write_gate.pending_write_from_react",
                return_value={"tool": "email_send", "args": {}, "result": {}},
            ):
                return await materialize_react_write_approval_turn(
                    settings=SimpleNamespace(),
                    org_id=ORG,
                    conversation_id=CONV,
                    client=_db(),
                    react_result=SimpleNamespace(tool_calls=[]),
                )

        with pytest.raises(SpeculativeSideEffectBlocked):
            await _in_scope(scope, _run)
        assert scope.blocked

    @pytest.mark.asyncio
    async def test_outside_a_run_nothing_is_blocked_or_deferred(self):
        block_if_speculative("anything")  # no scope: no-op
        deferred, result = await run_or_defer("x", lambda: asyncio.sleep(0, result=7))
        assert (deferred, result) == (False, 7)


class TestScopePropagationAndLifecycle:
    @pytest.mark.asyncio
    async def test_scope_reaches_threads_io_pool_and_bridge_loop(self):
        from app.core.async_bridge import run_coro_sync
        from app.core.io_pool import run_io

        scope = SpeculativeScope()

        async def _probe():
            return current_scope()

        def _sync_bridge():
            return run_coro_sync(_probe(), timeout=5)

        async def _run():
            return (
                await asyncio.to_thread(current_scope),
                await run_io(current_scope),
                await asyncio.to_thread(_sync_bridge),
            )

        assert await _in_scope(scope, _run) == (scope, scope, scope)

    @pytest.mark.asyncio
    async def test_straggler_task_of_a_discarded_run_cannot_write(self):
        db, svc, scope = _db(), _state_service(), SpeculativeScope()
        release = asyncio.Event()
        straggler: list[asyncio.Task] = []

        async def _late_write():
            await release.wait()
            await svc.update_task_state(CONV, ORG, {"active_objective": {"goal": "late"}}, client=db)

        async def _run():
            straggler.append(asyncio.create_task(_late_write()))

        await _in_scope(scope, _run)
        scope.discard()
        release.set()
        await straggler[0]
        assert db.writes == []
        assert scope.deferred == []

    @pytest.mark.asyncio
    async def test_after_adoption_writes_pass_through_in_order(self):
        db, svc, scope = _db(), _state_service(), SpeculativeScope()
        go_on = asyncio.Event()

        async def _run():
            await svc.update_task_state(CONV, ORG, {"rejected_options": ["early"]}, client=db)
            await go_on.wait()
            await svc.update_task_state(CONV, ORG, {"rejected_options": ["late"]}, client=db)

        task = asyncio.create_task(_in_scope(scope, _run))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert db.writes == []
        await scope.commit()
        go_on.set()
        await task
        assert db.tables["conversations"][0]["task_state"]["rejected_options"] == ["early", "late"]
        assert current_scope() is None

    @pytest.mark.asyncio
    async def test_writes_made_during_the_replay_queue_behind_it(self):
        """The producer resumes at adoption, before commit() has replayed the
        deferred writes; a write it makes then must not overtake them."""
        from app.services.speculative_execution import defer_if_speculative

        scope = SpeculativeScope()
        order: list[str] = []
        release = asyncio.Event()

        async def _older():
            await release.wait()
            order.append("older")

        scope.defer("older", _older)
        commit = asyncio.create_task(scope.commit())
        await asyncio.sleep(0)
        assert scope.flushing

        def _producer_write():
            if not defer_if_speculative("newer", order.append, "newer"):
                order.append("newer")
            # An adopted run may perform connector writes and approvals.
            block_if_speculative("connector_write")

        with speculative_scope(scope):
            _producer_write()
        release.set()
        assert await commit == 2
        assert order == ["older", "newer"]
        assert not scope.flushing
        with speculative_scope(scope):
            assert current_scope() is None
