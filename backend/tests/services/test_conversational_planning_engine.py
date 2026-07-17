"""Tests for ConversationalPlanningEngine."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.conversational_planning_engine import (
    ConversationalPlanningEngine,
    is_direct_connector_write_intent,
)


@pytest.mark.asyncio
async def test_create_plan_enriches_risks_and_confidence():
    engine = ConversationalPlanningEngine(settings=MagicMock())
    engine._planner = AsyncMock()
    engine._planner.create_plan = AsyncMock(
        return_value={
            "steps": [{"step_id": "s1", "description": "Analyze pipeline", "requires_approval": True}],
            "confidence": 0.6,
        }
    )
    engine._decision = AsyncMock()
    engine._decision.recommend_next_action = AsyncMock(
        return_value={
            "recommendations": [
                {"title": "Pipeline risk", "confidence": 0.7, "estimated_impact": "high"},
                {"title": "Coverage gap", "confidence": 0.5, "estimated_impact": "medium"},
            ]
        }
    )

    plan = await engine.create_plan("org-1", "user-1", "conv-1", "Improve sales pipeline", {})
    assert plan["risks"]
    assert plan["approvals_required"] == ["s1"]
    assert plan["confidence"] == pytest.approx(0.6)


def test_format_plan_section_includes_goal_and_risks():
    engine = ConversationalPlanningEngine(settings=MagicMock())
    section = engine.format_plan_section(
        {
            "goal": "Improve retention",
            "steps": [{"step_id": "s1", "description": "Audit churn drivers"}],
            "risks": [{"title": "Data gap", "summary": "Missing product usage signals"}],
            "confidence": 0.72,
        }
    )
    assert "Improve retention" in section
    assert "Data gap" in section
    assert "0.72" in section


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "classification", "expected"),
    [
        (
            "Create an Apollo contact list named exactly 'MSP Prospects'. Please plan the steps before executing.",
            {"requires_action": True, "intent": "workflow_execution"},
            False,
        ),
        (
            "Create an Apollo contact list named exactly 'MSP Prospects'. Do not invent a different name.",
            {"requires_action": True, "intent": "workflow_execution"},
            False,
        ),
        (
            "Send a Slack message to #general saying hello",
            {"requires_action": True, "intent": "workflow_execution"},
            False,
        ),
        (
            "How can we improve our outbound pipeline this quarter?",
            {"requires_action": False, "intent": "research"},
            True,
        ),
        (
            "Draft a plan to prioritize marketing channels",
            {"requires_action": False, "intent": "research"},
            True,
        ),
        (
            "Please plan the steps before executing the contact review",
            {"requires_action": False, "intent": "research"},
            False,  # bare "plan" no longer triggers; no strategic phrase hit
        ),
    ],
)
async def test_should_plan_skips_direct_writes_and_bare_plan(query, classification, expected):
    engine = ConversationalPlanningEngine(settings=MagicMock())
    assert await engine.should_plan(classification, query) is expected


def test_is_direct_connector_write_intent_list_create():
    assert is_direct_connector_write_intent(
        "Create an Apollo contact list named exactly 'x'. Please plan the steps before executing."
    )
    assert not is_direct_connector_write_intent("How can we improve retention?")
