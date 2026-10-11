"""Task-state writes that rebuild whole keys must start from the stored state.

Engineering pass 2026-10-11, findings 1a, 1b and 3a:

1a. Conversation memory was read (failing open to defaults), edited, then
    saved whole: one failed read wiped preferences and rejections, and two
    writers in the same moment lost one entry.
1b. A connector write's outcome record was built from a snapshot read before
    the provider call and verification: a newer draft saved meanwhile was
    overwritten with "executed" for the older write.
3a. The record of a write that really went out was dropped when its turn was
    cancelled (barge-in, stop), so a retry could not see it and could send
    the same thing twice.
"""
from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from app.services.action_lifecycle import (
    existing_successful_write,
    pending_superseded_by_newer_task,
    persist_write_outcome_patch,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.conversation_memory_engine import ConversationMemoryEngine
from app.services.conversation_state_service import ConversationStateService
from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation
from tests.services.fake_supabase_db import FakeSupabaseDB

ORG = "11111111-1111-4111-8111-111111111111"
CONV = "33333333-3333-4333-8333-333333333333"
SETTINGS = SimpleNamespace(
    supabase_url="https://test.supabase.co",
    supabase_anon_key="anon-test",
    supabase_service_role_key="service-role-test",
)

SEND = ConnectorActionPlan(
    tool_name="gmail_messages_send",
    invoke_action="gmail.messages.send",
    integration="gmail",
    kind="write",
    label="Send email",
    args={"to": "pat@example.com", "subject": "Quick update", "body": "Ready for review."},
    requires_approval=True,
)


class _FlakyDB(FakeSupabaseDB):
    """Selects fail ``fail_selects`` times, then behave; ``slow_select`` delays them."""

    def __init__(self, *, fail_selects: int = 0, slow_select: float = 0.0) -> None:
        super().__init__()
        self.fail_selects = fail_selects
        self.slow_select = slow_select
        self._count_lock = threading.Lock()

    def table(self, name: str) -> Any:
        query = super().table(name)
        db = self
        real_execute = query.execute

        def execute() -> Any:
            if query._op == "select":
                with db._count_lock:
                    failing = db.fail_selects > 0
                    if failing:
                        db.fail_selects -= 1
                if failing:
                    raise ConnectionError("read timed out")
                if db.slow_select:
                    time.sleep(db.slow_select)
            return real_execute()

        query.execute = execute
        return query


def _db(task_state: dict[str, Any], **kw: Any) -> _FlakyDB:
    db = _FlakyDB(**kw)
    db.tables["conversations"] = [{"id": CONV, "org_id": ORG, "task_state": task_state}]
    return db


def _stored(db: FakeSupabaseDB) -> dict[str, Any]:
    return db.tables["conversations"][0]["task_state"]


def _patched(db: FakeSupabaseDB) -> Any:
    return patch("app.services.conversation_state_service.get_supabase_client", lambda _s=None: db)


MEMORY = {
    "preferences": {"tone": "brief"},
    "rejected_recommendations": [{"text": "Build a stale-deal workflow", "reason": None}],
    "successful_actions": [{"action": "Sent the weekly report", "connector": "gmail"}],
}


# ---------------------------------------------------------------------------
# 1a. Conversation memory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_failed_memory_read_never_wipes_stored_memory() -> None:
    db = _db({"conversation_memory": dict(MEMORY)}, fail_selects=1)
    with _patched(db):
        engine = ConversationMemoryEngine(SETTINGS)
        await engine.record_action_outcome(CONV, ORG, action="Send email", success=False, connector="gmail")
    memory = _stored(db)["conversation_memory"]
    assert memory["preferences"] == {"tone": "brief"}
    assert memory["rejected_recommendations"] == MEMORY["rejected_recommendations"]
    assert memory["successful_actions"] == MEMORY["successful_actions"]
    assert memory["failed_actions"] == [{"action": "Send email", "connector": "gmail"}]


@pytest.mark.asyncio
async def test_unknown_state_saves_nothing_rather_than_defaults() -> None:
    db = _db({"conversation_memory": dict(MEMORY)}, fail_selects=10)
    with _patched(db):
        engine = ConversationMemoryEngine(SETTINGS)
        await engine.record_preference(CONV, ORG, "tone", "detailed")
    assert db.writes == []
    assert _stored(db)["conversation_memory"] == MEMORY


@pytest.mark.asyncio
async def test_concurrent_memory_writers_both_keep_their_entries() -> None:
    db = _db({"conversation_memory": dict(MEMORY)}, slow_select=0.05)
    with _patched(db):
        engine = ConversationMemoryEngine(SETTINGS)
        await asyncio.gather(
            engine.record_action_outcome(CONV, ORG, action="Create the deal", success=True, connector="hubspot"),
            engine.record_action_outcome(CONV, ORG, action="Post the summary", success=True, connector="slack"),
        )
    actions = [row["action"] for row in _stored(db)["conversation_memory"]["successful_actions"]]
    assert actions == ["Sent the weekly report", "Create the deal", "Post the summary"] or actions == [
        "Sent the weekly report",
        "Post the summary",
        "Create the deal",
    ]


# ---------------------------------------------------------------------------
# 1b. Write outcomes built from fresh state
# ---------------------------------------------------------------------------


def _executing() -> dict[str, Any]:
    return {
        "type": "connector_action",
        "status": "executing",
        "execution_claim_id": "claim-1",
        "actor_id": "user-1",
        "params": {"invoke_action": SEND.invoke_action, "args": dict(SEND.args)},
    }


def _outcome(state: dict[str, Any], *, pending_at_start: dict[str, Any] | None) -> dict[str, Any]:
    return persist_write_outcome_patch(
        task_state=state,
        connector_plan=SEND,
        success=True,
        summary="Sent.",
        structured={"id": "msg-1"},
        pending_task={"type": "connector_action", "status": "executed"},
        verification={"verified": True},
        pending_at_start=pending_at_start,
    )


def test_the_outcome_marks_its_own_task_executed() -> None:
    claimed = _executing()
    patch_ = _outcome({"pending_task": claimed}, pending_at_start={**claimed, "status": "awaiting_confirm"})
    assert patch_["pending_task"]["status"] == "executed"
    assert patch_["pending_task"]["params"]["args"]["to"] == "pat@example.com"


def test_a_newer_draft_survives_a_late_outcome_and_the_send_is_still_recorded() -> None:
    at_start = {
        "type": "connector_action",
        "status": "awaiting_params",
        "params": {"invoke_action": SEND.invoke_action, "args": dict(SEND.args)},
    }
    newer = {
        "type": "connector_action",
        "status": "awaiting_params",
        "params": {"invoke_action": "hubspot.deals.create", "args": {"dealname": "Acme"}},
    }
    state = {"pending_task": newer, "execution_observations": [{"step_id": "older", "success": True}]}
    assert pending_superseded_by_newer_task(state, SEND, pending_at_start=at_start)
    patch_ = _outcome(state, pending_at_start=at_start)
    assert "pending_task" not in patch_ and "execution_plan" not in patch_
    steps = [row["step_id"] for row in patch_["execution_observations"]]
    assert "older" in steps and len(steps) == 2
    # The send is still on record, so a retry of it is recognised as done.
    assert existing_successful_write({**state, **patch_}, invoke_action=SEND.invoke_action)


def test_a_corrected_detail_counts_as_a_newer_draft() -> None:
    at_start = {"type": "connector_action", "status": "awaiting_params", "params": {"args": dict(SEND.args)}}
    corrected = {
        "type": "connector_action",
        "status": "awaiting_params",
        "params": {"args": {**SEND.args, "subject": "Revised update"}},
    }
    assert pending_superseded_by_newer_task({"pending_task": corrected}, SEND, pending_at_start=at_start)
    # The same draft as at the start is this write's own task, even after a
    # save re-derived its plan projection fields.
    reprojected = {**at_start, "_projection": True, "plan_id": "p-2"}
    assert not pending_superseded_by_newer_task({"pending_task": reprojected}, SEND, pending_at_start=at_start)


@pytest.mark.asyncio
async def test_the_outcome_is_built_from_the_state_read_under_the_lock() -> None:
    newer = {"type": "connector_action", "status": "awaiting_params", "params": {"invoke_action": "hubspot.deals.create"}}
    db = _db({"pending_task": _executing(), "execution_observations": [{"step_id": "older", "success": True}]})
    with _patched(db):
        service = ConversationStateService(SETTINGS)
        # A newer draft lands between the provider call and the outcome save.
        await service.update_task_state(CONV, ORG, {"pending_task": newer})
        newer_as_saved = _stored(db)["pending_task"]
        await service.update_task_state_from(
            CONV, ORG, lambda s: _outcome(s, pending_at_start=_executing()), effect_record=True
        )
    stored = _stored(db)
    assert stored["pending_task"] == newer_as_saved
    assert stored["pending_task"]["params"]["invoke_action"] == "hubspot.deals.create"
    assert [row["step_id"] for row in stored["execution_observations"]][0] == "older"
    assert len(stored["execution_observations"]) == 2


# ---------------------------------------------------------------------------
# 3a. Records of real effects survive a cancelled turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_cancelled_turn_keeps_the_record_of_a_send_that_went_out() -> None:
    db = _db({"pending_task": _executing()})
    token = TurnCancellation()
    token.cancel("barge_in")
    with _patched(db), bound_turn_cancellation(token):
        service = ConversationStateService(SETTINGS)
        # Ordinary turn state from the cancelled turn is still dropped.
        await service.update_task_state(CONV, ORG, {"current_plan": {"objective": "stale"}})
        assert _stored(db).get("current_plan") is None
        await service.update_task_state_from(
            CONV, ORG, lambda s: _outcome(s, pending_at_start=None), effect_record=True
        )
    stored = _stored(db)
    assert stored["pending_task"]["status"] == "executed"
    assert existing_successful_write(stored, invoke_action=SEND.invoke_action)


# ---------------------------------------------------------------------------
# 3a. A cancelled turn: a dispatched write finishes and records; an
#     undispatched one never starts
# ---------------------------------------------------------------------------


def _connector_service(registry_call: Any) -> Any:
    from unittest.mock import AsyncMock, MagicMock

    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    service = ChatConnectorExecutionService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.update_task_state_from = AsyncMock()
    service._state.get_task_state = AsyncMock(return_value={"pending_task": None})
    service._state.compare_and_set_pending_status = AsyncMock(return_value=True)
    registry = MagicMock()
    registry.execute_invoke_action = registry_call
    service._registry = registry
    service._finalize_connector_outcome = MagicMock(return_value=None)
    service._record_outcomes = AsyncMock()
    service._persist_recent_connector_invocation = AsyncMock()
    service._claim_write_before_invoke = AsyncMock(return_value=None)
    return service


_APPROVAL_FREE_SEND = ConnectorActionPlan(
    tool_name="slack_chat_post_message",
    invoke_action="slack.chat.postMessage",
    integration="slack",
    kind="write",
    label="Post to Slack",
    args={"channel": "C1", "text": "Shipped."},
    requires_approval=False,
)


async def _run_and_cancel(service: Any, token: TurnCancellation, *, cancel_after: float) -> None:
    async def turn() -> Any:
        with bound_turn_cancellation(token):
            return await service.execute_plan(
                org_id=ORG,
                user_id="user-1",
                conversation_id=CONV,
                plan=_APPROVAL_FREE_SEND,
                client=object(),
                classification={},
            )

    with patch("app.services.approval_action_binding.assert_plan_matches_binding", lambda *a, **k: None):
        task = asyncio.ensure_future(turn())
        await asyncio.sleep(cancel_after)
        token.cancel("barge_in")
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        from app.services import chat_connector_execution_service as module

        for _ in range(50):
            if not module._DETACHED_WRITES:
                break
            await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_a_write_cut_off_mid_call_still_records_its_outcome() -> None:
    from unittest.mock import AsyncMock

    calls: list[str] = []

    async def provider(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs["invoke_action"])
        await asyncio.sleep(0.15)
        return {"success": True, "connector_id": "conn-1", "result": {"ts": "1.2"}}

    service = _connector_service(AsyncMock(side_effect=provider))
    await _run_and_cancel(service, TurnCancellation(), cancel_after=0.05)
    assert calls == ["slack.chat.postMessage"]
    service._state.update_task_state_from.assert_awaited()
    assert service._state.update_task_state_from.await_args.kwargs["effect_record"] is True


@pytest.mark.asyncio
async def test_a_write_cancelled_before_the_call_never_reaches_the_provider() -> None:
    from unittest.mock import AsyncMock

    calls: list[str] = []
    started = asyncio.Event()

    async def slow_state(*_a: Any, **_k: Any) -> dict[str, Any]:
        started.set()
        await asyncio.sleep(0.1)
        return {"pending_task": None}

    async def provider(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs["invoke_action"])
        return {"success": True}

    service = _connector_service(AsyncMock(side_effect=provider))
    service._state.get_task_state = AsyncMock(side_effect=slow_state)
    await _run_and_cancel(service, TurnCancellation(), cancel_after=0.03)
    assert calls == []
