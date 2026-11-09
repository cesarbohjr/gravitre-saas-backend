"""Tests for unified-turn live → classical ReAct fallthrough."""
from __future__ import annotations

from app.services.unified_turn_classical_fallback import (
    message_requires_classical_tool_sse,
    should_defer_unified_turn_live_to_classical,
)


def test_message_requires_classical_tool_sse_connectors():
    assert message_requires_classical_tool_sse("What connectors are connected right now?")


def test_agent_mode_pure_chat_not_deferred():
    """Connectors upgrade standard→agent; LIVE must still own greetings."""
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="agent",
        outcome_kind="conversational_reply",
        message="Hey",
    )


def test_reasoning_mode_pure_chat_not_deferred():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="reasoning",
        outcome_kind="conversational_reply",
        message="hello",
    )


def test_standard_mode_pure_chat_not_deferred():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="hello",
    )


def test_standard_greeting_not_deferred_when_requires_action_flag_set():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="Hey",
        classification={"requires_action": True},
    )


def test_defer_connector_tool_proposal_all_modes():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="connector_tool_proposal",
        message="create an apollo contact list",
    )


def test_fast_mode_pure_chat_not_deferred():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message="hey there",
    )


def test_fast_mode_connector_query_deferred():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message="What connectors are connected right now?",
    )


def test_standard_mode_connector_query_deferred():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="What connectors are connected right now?",
    )


def test_agent_mode_connector_query_deferred():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="agent",
        outcome_kind="conversational_reply",
        message="What connectors are connected right now?",
    )


def test_explicit_live_no_defer_cannot_be_overridden_by_legacy_wording():
    """ECO-011 / DEC-001: one authoritative routing decision per turn."""
    for outcome_kind in ("conversational_reply", "clarifying_question", "knowledge_boundary"):
        assert not should_defer_unified_turn_live_to_classical(
            mode_key="agent",
            outcome_kind=outcome_kind,
            message="What connectors are connected right now?",
            classification={"requires_action": False},
            needs_tool_sse=False,
        )


def test_explicit_structured_defer_honored_without_keyword_matching():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="Investigate unusual renewal risk",
        needs_tool_sse=True,
    )


def test_legacy_callers_without_structured_signal_keep_guarded_compatibility():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="What connectors are connected right now?",
        needs_tool_sse=None,
    )
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="Hey, how are you?",
        needs_tool_sse=None,
    )


def test_connector_proposal_stays_live_even_when_sse_signal_is_true():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="agent",
        outcome_kind="connector_tool_proposal",
        message="Send the approved email",
        needs_tool_sse=True,
    )


def test_human_venting_remains_live_even_if_structured_signal_is_true():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="agent",
        outcome_kind="conversational_reply",
        message="This has been such a frustrating day. I'm exhausted.",
        needs_tool_sse=True,
    )


def test_handoff_consumed_once_and_removed_from_persistable_state():
    """ECO-011/DEC-018: a retry cannot re-arm a consumed tool selection."""
    from types import SimpleNamespace
    from app.services.live_classical_handoff import (
        arm_from_task_state, consume_handoff, peek_handoff,
        stash_live_classical_handoff,
    )

    state = {}
    try:
        proposal = SimpleNamespace(
            tool_name="getConnectorStatus", tool_invoke_action="getConnectorStatus",
            tool_arguments={"provider": "slack"},
        )
        stashed = stash_live_classical_handoff(
            state, proposal, reason="read_tool_classical",
        )
        assert stashed is not None
        arm_from_task_state(state)
        assert "live_classical_handoff" not in state
        assert consume_handoff() == stashed
        assert consume_handoff() is None
        arm_from_task_state(state)  # simulated retry with same conversation state
        assert peek_handoff() is None
        assert consume_handoff() is None
    finally:
        arm_from_task_state({})  # contextvars must not leak across tests


def test_evidence_queue_consumes_each_choice_once_without_stale_rearm():
    """DEC-002/018: queued handoff choices have bounded one-shot semantics."""
    from app.services.live_classical_handoff import (
        arm_from_task_state, consume_handoff, stash_handoff_queue,
    )

    state = {}
    try:
        stash_handoff_queue(state, [
            {"tool_name": "first_read", "tool_arguments": {"step": 1}},
            {"tool_name": "second_read", "tool_arguments": {"step": 2}},
        ])
        arm_from_task_state(state)
        assert "live_classical_handoff_queue" not in state
        assert "live_classical_handoff" not in state
        assert "evidence_plan_owns_tools" not in state
        assert consume_handoff()["tool_name"] == "first_read"
        assert consume_handoff()["tool_name"] == "second_read"
        assert consume_handoff() is None
        arm_from_task_state(state)
        assert consume_handoff() is None
    finally:
        arm_from_task_state({})


def test_new_direct_handoff_replaces_unconsumed_prior_queue():
    """DEC-001: a new turn must never inherit the previous turn's queued action."""
    from app.services.live_classical_handoff import (
        arm_from_task_state, arm_handoff, consume_handoff, stash_handoff_queue,
    )

    try:
        state = {}
        stash_handoff_queue(state, [{"tool_name": "stale_read"}])
        arm_from_task_state(state)
        arm_handoff({"tool_name": "current_read", "tool_arguments": {}})
        assert consume_handoff()["tool_name"] == "current_read"
        assert consume_handoff() is None
    finally:
        arm_from_task_state({})
