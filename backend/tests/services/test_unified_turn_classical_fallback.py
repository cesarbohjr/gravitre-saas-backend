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
    assert should_defer_unified_turn_live_to_classical(
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
