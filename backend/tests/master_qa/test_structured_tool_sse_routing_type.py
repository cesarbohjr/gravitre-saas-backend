"""Structured LIVE tool-SSE decisions must not be overridden by truthiness."""

import pytest

from app.services.unified_turn_classical_fallback import (
    should_defer_unified_turn_live_to_classical,
)


def decide(signal, message="Post a Slack message"):
    return should_defer_unified_turn_live_to_classical(
        mode_key="agent",
        outcome_kind="conversational_reply",
        message=message,
        needs_tool_sse=signal,
    )


def test_explicit_false_wins_over_keyword_heuristic():
    assert decide(False) is False


def test_explicit_true_requests_guarded_handoff():
    assert decide(True) is True


@pytest.mark.parametrize("invalid", ["false", "true", 0, 1, [], {}])
def test_nonboolean_signal_cannot_select_execution_path(invalid):
    with pytest.raises(TypeError, match="needs_tool_sse must be a boolean or None"):
        decide(invalid)


def test_connector_tool_proposal_remains_live():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="agent",
        outcome_kind="connector_tool_proposal",
        message="Send an email",
        needs_tool_sse=True,
    ) is False
