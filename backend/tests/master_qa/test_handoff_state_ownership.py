"""A consumed LIVE choice cannot survive in serialized conversation task state.

Exercises the real handoff adapter without a model, provider or database. These
are dispatch-ownership contracts, not certification of provider idempotency.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from app.services.live_classical_handoff import (
    arm_from_task_state, consume_handoff, stash_handoff_queue,
    stash_live_classical_handoff,
)


def _choice(name):
    return {"tool_name": name, "tool_arguments": {"limit": 2}}


def test_consumed_selection_cannot_rearm_from_serialized_task_state():
    state = {"pending_task": {"status": "awaiting_approval"}}
    stash_live_classical_handoff(
        state, SimpleNamespace(**_choice("hubspot.contacts.search")),
        reason="read_tool_classical",
    )
    arm_from_task_state(state)
    assert consume_handoff()["tool_name"] == "hubspot.contacts.search"
    assert consume_handoff() is None
    # This is the state that can be returned to the conversation and loaded on
    # the next turn. Approval ownership must remain intact while the transient
    # selection disappears.
    resumed = json.loads(json.dumps(state))
    arm_from_task_state(resumed)
    assert consume_handoff() is None
    assert resumed == {"pending_task": {"status": "awaiting_approval"}}


def test_interrupted_queue_cannot_override_next_turn_selection():
    state = {"execution_plan": {"id": "canonical-plan"}}
    stash_handoff_queue(state, [_choice("hubspot.contacts.search"), _choice("google_ads.reports.performance")])
    arm_from_task_state(state)
    assert consume_handoff()["tool_name"] == "hubspot.contacts.search"
    # Stop before the remaining read. A new turn must not inherit either the
    # queued read or evidence-plan ownership that would reject its new choice.
    stash_live_classical_handoff(
        state, SimpleNamespace(**_choice("slack.conversations.list")),
        reason="read_tool_classical",
    )
    arm_from_task_state(state)
    assert consume_handoff()["tool_name"] == "slack.conversations.list"
    assert consume_handoff() is None
    assert state == {"execution_plan": {"id": "canonical-plan"}}


def test_current_queue_transfers_all_choices_in_order_once():
    state = {}
    stash_handoff_queue(state, [_choice("hubspot.contacts.search"), _choice("google_ads.reports.performance")])
    arm_from_task_state(state)
    assert state == {}
    assert [consume_handoff()["tool_name"], consume_handoff()["tool_name"]] == [
        "hubspot.contacts.search", "google_ads.reports.performance",
    ]
    assert consume_handoff() is None
    arm_from_task_state(state)
    assert consume_handoff() is None


def test_abandoned_selection_requires_fresh_reasoning_before_retry():
    state = {}
    stash_handoff_queue(state, [_choice("hubspot.contacts.search")])
    arm_from_task_state(state)
    # Cancellation can precede the first ReAct iteration. There is no provider
    # result to resume; a retry must acquire a new authorized selection.
    arm_from_task_state(json.loads(json.dumps(state)))
    assert consume_handoff() is None


def test_overlapping_turns_keep_their_transferred_queues_isolated():
    async def run():
        ready = asyncio.Event()
        count = 0

        async def turn(name):
            nonlocal count
            state = {}
            stash_handoff_queue(state, [_choice(name), _choice(name + ".followup")])
            arm_from_task_state(state)
            count += 1
            if count == 2:
                ready.set()
            await ready.wait()
            result = [consume_handoff()["tool_name"], consume_handoff()["tool_name"]]
            assert consume_handoff() is None
            assert state == {}
            return result

        return await asyncio.gather(turn("tenant-a.read"), turn("tenant-b.read"))

    assert asyncio.run(run()) == [
        ["tenant-a.read", "tenant-a.read.followup"],
        ["tenant-b.read", "tenant-b.read.followup"],
    ]
