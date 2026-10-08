"""Regression tests for the guarded spoken low-latency path."""

from app.services.operator_task_intent import use_spoken_lite_path


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
