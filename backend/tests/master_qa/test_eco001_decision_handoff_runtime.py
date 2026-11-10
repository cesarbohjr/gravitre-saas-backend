"""ECO-001 / DEC-001 / DEC-018: behavioral single-decision handoff contracts.

Runs real routing + one-shot handoff functions with no network or provider.
This is bounded runtime behavior, NOT deployed caller or end-to-end proof.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.services.unified_turn_classical_fallback import (
    should_defer_unified_turn_live_to_classical,
)
from app.services.live_classical_handoff import (
    arm_from_task_state, consume_handoff, fake_tool_choice_response,
    stash_live_classical_handoff,
)


def test_structured_routing_is_only_authority_for_text_handoff():
    task = "Post a Slack message to our marketing channel"
    # Explicit LIVE false must defeat the former message-regex second vote.
    assert should_defer_unified_turn_live_to_classical(
        mode_key="standard", outcome_kind="conversational_reply",
        message=task, needs_tool_sse=False,
    ) is False
    assert should_defer_unified_turn_live_to_classical(
        mode_key="standard", outcome_kind="conversational_reply",
        message=task, needs_tool_sse=True,
    ) is True
    # A connector write proposal remains on LIVE to obtain governed approval,
    # even if another classifier erroneously marks a classical tool requirement.
    assert should_defer_unified_turn_live_to_classical(
        mode_key="standard", outcome_kind="connector_tool_proposal",
        message=task, needs_tool_sse=True,
    ) is False


def test_live_decision_transfers_exactly_one_selected_tool_to_classical():
    state = {}
    selected = SimpleNamespace(
        tool_name="hubspot.contacts.search",
        tool_invoke_action="hubspot.contacts.search",
        tool_arguments={"query": "qa-routing"},
    )
    try:
        assert should_defer_unified_turn_live_to_classical(
            mode_key="standard", outcome_kind="conversational_reply",
            message="Search contacts", needs_tool_sse=True,
        )
        stash_live_classical_handoff(
            state, selected, reason="defer_classical_tool_sse",
        )
        arm_from_task_state(state)
        assert "live_classical_handoff" not in state
        payload = consume_handoff()
        assert payload and payload["tool_name"] == selected.tool_name
        assert payload["tool_arguments"] == selected.tool_arguments
        actual = fake_tool_choice_response(payload)
        choice = actual.choices[0].message.tool_calls[0]
        assert choice.function.name == selected.tool_name
        assert '"qa-routing"' in choice.function.arguments
        assert consume_handoff() is None
        # Empty re-arm after a later turn must not resurrect a previous choice.
        arm_from_task_state({})
        assert consume_handoff() is None
    finally:
        arm_from_task_state({})


def test_two_concurrent_turn_contexts_cannot_consume_each_other_handoff():
    async def turn(tool_name: str) -> tuple[str, bool]:
        state = {}
        stash_live_classical_handoff(
            state,
            SimpleNamespace(tool_name=tool_name, tool_invoke_action=tool_name, tool_arguments={}),
            reason="read_tool_classical",
        )
        arm_from_task_state(state)
        await asyncio.sleep(0)
        received = consume_handoff()
        return str(received["tool_name"]), consume_handoff() is None

    async def both():
        return await asyncio.gather(turn("hubspot.deals.list"), turn("gmail.messages.list"))

    try:
        assert asyncio.run(both()) == [
            ("hubspot.deals.list", True),
            ("gmail.messages.list", True),
        ]
    finally:
        arm_from_task_state({})
