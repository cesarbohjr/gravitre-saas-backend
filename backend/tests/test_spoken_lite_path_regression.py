"""Regression tests for the guarded spoken low-latency path.

Ported from the earlier restore attempt with its expectations corrected: a
connector/business read ("How many companies are in my HubSpot?") is deep
and runs in agent mode, not medium/fast. It names a connector and asks for a
count of the org's own records, which needs the connector tool and the full
pipeline; fast mode would answer it from a reduced toolset.
"""

from app.services.conversation_tier import classify_conversation_tier
from app.services.operator_task_intent import (
    resolve_voice_session_intelligence_mode,
    use_spoken_lite_path,
)


def test_simple_spoken_turn_uses_lite_path():
    assert use_spoken_lite_path(spoken_mode=True, routing_tier="simple", message="Hello!")


def test_small_talk_beyond_exact_phrases_uses_lite_path():
    for message in ("hey, how was your weekend?", "haha that's funny", "tell me a joke"):
        assert use_spoken_lite_path(spoken_mode=True, routing_tier="simple", message=message), message


def test_non_spoken_turn_stays_full():
    assert not use_spoken_lite_path(spoken_mode=False, routing_tier="simple", message="Hello")


def test_empty_spoken_turn_does_not_run():
    assert not use_spoken_lite_path(spoken_mode=True, routing_tier="simple", message=" ")


def test_complex_route_stays_full():
    assert not use_spoken_lite_path(spoken_mode=True, routing_tier="complex", message="Hello")


def test_operator_task_stays_full():
    assert not use_spoken_lite_path(
        spoken_mode=True,
        routing_tier="simple",
        message="Create four campaigns in Google Ads, but don't execute without my approval",
    )


def test_business_read_stays_on_full_reasoning():
    assert not use_spoken_lite_path(
        spoken_mode=True,
        routing_tier="simple",
        message="How many companies are in my HubSpot?",
    )


def test_unsolicited_context_not_assumed_simple():
    assert not use_spoken_lite_path(
        spoken_mode=True,
        routing_tier="simple",
        message="Tell me what happened in my account",
    )


def test_pending_approval_keeps_full_pipeline():
    state = {"pending_action": {"id": "pa-1", "status": "awaiting_user"}}
    assert not use_spoken_lite_path(spoken_mode=True, routing_tier="simple", message="thanks!", task_state=state)


def test_light_medium_deep_voice_routing():
    assert classify_conversation_tier("Hello!").tier == "light"
    assert classify_conversation_tier("How does onboarding work?").tier == "medium"
    assert classify_conversation_tier("How many companies are in my HubSpot?").tier == "deep"
    assert classify_conversation_tier("Investigate my production logs").tier == "deep"
    assert classify_conversation_tier("Create four campaigns in Google Ads").tier == "deep"
    assert resolve_voice_session_intelligence_mode("Hello!") == "fast"
    assert resolve_voice_session_intelligence_mode("How does onboarding work?") == "standard"
    assert resolve_voice_session_intelligence_mode("How many companies are in my HubSpot?") == "agent"
    assert resolve_voice_session_intelligence_mode("Investigate my production logs") == "agent"


def test_definitional_question_is_not_deep():
    assert classify_conversation_tier("what does merge mean in git?").tier == "medium"


def test_empty_message_defaults_medium():
    assert classify_conversation_tier(" ").tier == "medium"
