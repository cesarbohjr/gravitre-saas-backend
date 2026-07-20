"""Advisory plan-first must stage current_plan, not connector short-circuit."""
from __future__ import annotations

import asyncio

from app.services.conversational_planning_engine import (
    ConversationalPlanningEngine,
    is_advisory_plan_first,
    is_direct_connector_write_intent,
)
from app.services.connector_chat_routing import should_run_connector_preflight


ADVISORY_APOLLO = (
    "Make a strategic multi-step plan to create an Apollo contact list "
    "for MSP prospects, then enrich it, then notify Slack. "
    "Show the plan first — do not execute yet."
)


def test_advisory_phrases_detected():
    assert is_advisory_plan_first(ADVISORY_APOLLO)
    assert is_advisory_plan_first("outline the steps, do not execute yet")
    assert not is_advisory_plan_first("create an Apollo contact list now")


def test_advisory_is_not_direct_connector_write():
    assert is_direct_connector_write_intent(ADVISORY_APOLLO) is False


def test_advisory_should_plan_true():
    engine = ConversationalPlanningEngine()
    assert asyncio.run(engine.should_plan({"requires_action": True, "intent": "action"}, ADVISORY_APOLLO))


def test_advisory_skips_connector_preflight():
    assert (
        should_run_connector_preflight(
            {},
            message=ADVISORY_APOLLO,
            connected_integrations=[],
            routing_tier="research",
        )
        is False
    )


def test_advisory_skips_catalog_write_clarification():
    """Plan-first must not hijack into Slack channel / Gmail staging."""
    from app.services.clarification_engine import ClarificationEngine

    engine = ClarificationEngine()
    trigger = engine._rule_based_trigger(
        {
            "request": ADVISORY_APOLLO,
            "requires_action": True,
            "risk_level": "low",
            "classification_confidence": 0.9,
        },
        {"connected_integrations": []},
        {"connector_dependencies": ["slack", "apollo"]},
        {},
        0.9,
        task_state={"parameter_ledger": {"slots": {}, "pending_missing": []}},
    )
    assert trigger is None
