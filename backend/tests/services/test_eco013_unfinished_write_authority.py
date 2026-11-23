"""Terminal authority is independent of whether a stopped WRITE ran.

Actual bridge/loop/finalizer/state-writer code; storage is an in-memory double.
No provider, deployed cancellation timing, or database/RLS certification.
"""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.services.autonomous_execution_loop import decide_execution_loop
from app.services.conversation_state_service import ConversationStateService
from app.services.execution_plan_adapters import bridge_pending_task_with_plan
from app.services.execution_plan_authority import prefer_persisted_write_plan
from app.services.execution_plan_service import (
    ExecutionObservation, ExecutionPlan, continue_execution_plan, replan_execution_plan,
)
from app.services.react_execution_strategy import ReactPlanRuntime, finalize_react_execution_plan


def _terminal_from_actual_producer(status, step_status="pending"):
    plan, _, _ = bridge_pending_task_with_plan({
        "action": "gmail.messages.send", "requires_approval": True,
        "status": "awaiting_confirm", "connector_id": "gmail",
    })
    plan.revision = 5
    plan.steps = [replace(step, status=step_status) for step in plan.steps]
    runtime = ReactPlanRuntime(plan)
    if status == "cancelled":
        result = decide_execution_loop(plan=plan, task_state={"durable_session": {"phase": "CANCELLED"}})
        assert result.terminal and result.action == "stop"
        terminal = result.plan
    else:
        if status == "partial":
            runtime.observations = [ExecutionObservation(
                step_id="independent-read", connector_id="gmail", success=False, summary="Read failed",
            )]
        terminal, _ = finalize_react_execution_plan(
            runtime, react_status={"failed": "error", "blocked": "max_iterations_reached"}.get(status, "done"),
            answer="A model answer does not verify the pending write" if status == "verification_inconclusive" else "",
        )
    assert terminal.source == "pending_task_bridge"
    assert terminal.terminal_status == status
    assert terminal.steps[0].status == step_status
    return terminal


@pytest.mark.parametrize("status", ["cancelled", "blocked", "failed", "partial", "verification_inconclusive"])
@pytest.mark.parametrize("step_status", ["pending", "running"])
@pytest.mark.parametrize("revision", [4, 5])
def test_actual_terminal_producer_rejects_delayed_same_plan_patch(status, step_status, revision):
    current = _terminal_from_actual_producer(status, step_status)
    before = current.as_dict()
    delayed = replace(current, terminal_status="waiting_for_approval", revision=revision)
    assert prefer_persisted_write_plan(current, delayed) is current
    assert current.as_dict() == before


@pytest.mark.parametrize("status", ["cancelled", "blocked", "failed", "partial", "verification_inconclusive"])
def test_actual_terminal_with_unstarted_write_survives_continuation(status):
    current = _terminal_from_actual_producer(status)
    assert continue_execution_plan(current, message="yes").terminal_status == status
    assert continue_execution_plan(current, message="what happened?", follow_up=True).terminal_status == status


@pytest.mark.parametrize("status", ["cancelled", "verification_inconclusive"])
def test_weak_compose_cannot_replace_terminal_plan_with_unstarted_write(status):
    current = _terminal_from_actual_producer(status)
    compose = ExecutionPlan("late-compose", "Summarize", [], "default_compose", revision=6)
    assert prefer_persisted_write_plan(current, compose) is current
    assert current.terminal_status == status and current.steps[0].status == "pending"


class _Query:
    def __init__(self, db, payload=None):
        self.db, self.payload, self.filters = db, payload, {}

    def select(self, *_args):
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def filter(self, key, operator, value):
        assert operator == "is" and value == "null"
        self.filters[key] = None
        return self

    def limit(self, _count):
        return self

    def execute(self):
        assert self.filters["id"] == "conversation" and self.filters["org_id"] == "org"
        if self.payload is None:
            return SimpleNamespace(data=[{"task_state": deepcopy(self.db.state)}])
        self.db.writes += 1
        expected = self.filters["task_state->>task_revision"]
        if self.db.conflict is not None:
            self.db.state = deepcopy(self.db.conflict)
            self.db.conflict = None
        if str(expected) != str(self.db.state.get("task_revision")):
            return SimpleNamespace(data=[])
        self.db.state = deepcopy(self.payload["task_state"])
        return SimpleNamespace(data=[{"id": "conversation"}])


class _Db:
    def __init__(self, state, conflict=None):
        self.state, self.conflict, self.writes = deepcopy(state), deepcopy(conflict), 0

    def table(self, name):
        assert name == "conversations"
        return _Query(self)


@pytest.mark.asyncio
@pytest.mark.parametrize("conflict", [False, True])
async def test_actual_state_writer_rechecks_terminal_authority_after_revision_conflict(mock_settings, conflict):
    terminal = _terminal_from_actual_producer("cancelled")
    delayed = replace(terminal, terminal_status="waiting_for_approval", revision=4)
    stored = {"execution_plan": terminal.as_dict(), "task_revision": 9, "other_writer": "kept"}
    initial = {"execution_plan": delayed.as_dict(), "task_revision": 8} if conflict else stored
    db = _Db(initial, stored if conflict else None)
    await ConversationStateService(mock_settings).update_task_state(
        "conversation", "org", {"execution_plan": delayed.as_dict(),
        "pending_task": {"status": "awaiting_confirm", "requires_approval": True}}, client=db,
    )
    assert db.state["execution_plan"] == terminal.as_dict()
    assert db.state["pending_task"]["status"] == "cancelled"
    assert db.state["task_revision"] == 10
    assert db.state["other_writer"] == "kept"
    assert db.writes == (2 if conflict else 1)
    # A reconnect with only the stored plan still stops at the actual dispatch
    # decision. No provider/registry is reached or substituted in this check.
    replay = ReactPlanRuntime(ExecutionPlan.from_dict(db.state["execution_plan"]))
    with pytest.raises(RuntimeError, match="react_dispatch_blocked:cancelled"):
        replay.next_step_id("gmail_send_email", 0, is_write=True)


def test_distinct_action_and_newer_terminal_evidence_remain_supported():
    terminal = _terminal_from_actual_producer("verification_inconclusive")
    verified = replace(terminal, terminal_status="completed", revision=6)
    assert prefer_persisted_write_plan(terminal, verified) is verified
    distinct = replace(terminal, plan_id="separate-action", terminal_status="waiting_for_approval", revision=1)
    assert prefer_persisted_write_plan(terminal, distinct) is distinct
    replanned = replan_execution_plan(terminal, new_steps=terminal.steps, reason="explicit_replan")
    assert replanned.plan_id == terminal.plan_id and replanned.revision == 6
    # Preserve the existing policy: a nonterminal replan cannot erase prior terminal truth.
    assert prefer_persisted_write_plan(terminal, replanned) is terminal


def test_inflight_write_and_read_only_plan_are_not_frozen():
    write, _, _ = bridge_pending_task_with_plan({"action": "send", "requires_approval": True})
    running = replace(write, terminal_status="running")
    assert prefer_persisted_write_plan(write, running) is running
    read = ExecutionPlan("read", "Read", [replace(write.steps[0], kind="read")], "pending_task_bridge",
                         terminal_status="completed")
    new_read = replace(read, terminal_status="running", revision=2)
    assert prefer_persisted_write_plan(read, new_read) is new_read
