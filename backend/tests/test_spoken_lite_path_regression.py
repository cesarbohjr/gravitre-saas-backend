"""Regression tests for the guarded spoken low-latency path."""

from app.services.operator_task_intent import (use_spoken_lite_path, classify_spoken_conversation_tier, resolve_voice_session_intelligence_mode)


def test_simple_spoken_turn_uses_lite_path():
    assert use_spoken_lite_path(spoken_mode=True, routing_tier="simple", message="Hello!")


def test_non_spoken_turn_stays_full():
    assert not use_spoken_lite_path(spoken_mode=False, routing_tier="simple", message="Hello")


def test_empty_spoken_turn_does_not_run():
    assert not use_spoken_lite_path(spoken_mode=True, routing_tier="simple", message=" ")


def test_complex_route_stays_full():
    assert not use_spoken_lite_path(spoken_mode=True, routing_tier="complex", message="Hello")


def test_operator_task_stays_full():
    assert not use_spoken_lite_path(
        spoken_mode=True, routing_tier="simple",
        message="Create four campaigns in Google Ads, but don't execute without my approval",
    )


def test_business_read_stays_on_full_reasoning():
    assert not use_spoken_lite_path(
        spoken_mode=True, routing_tier="simple",
        message="How many companies are in my HubSpot?",
    )


def test_unsolicited_context_not_assumed_simple():
    assert not use_spoken_lite_path(
        spoken_mode=True, routing_tier="simple",
        message="Tell me what happened in my account",
    )


def test_light_medium_deep_voice_routing():
    assert classify_spoken_conversation_tier("Hello!") == "light"
    assert classify_spoken_conversation_tier("How does onboarding work?") == "medium"
    assert classify_spoken_conversation_tier("How many companies are in my HubSpot?") == "medium"
    assert classify_spoken_conversation_tier("Investigate my production logs") == "deep"
    assert classify_spoken_conversation_tier("Create four campaigns in Google Ads") == "deep"
    assert resolve_voice_session_intelligence_mode("Hello!") == "fast"
    assert resolve_voice_session_intelligence_mode("How many companies are in my HubSpot?") == "fast"
    assert resolve_voice_session_intelligence_mode("Investigate my production logs") == "agent"


def test_empty_message_defaults_medium():
    assert classify_spoken_conversation_tier(" ") == "medium"
