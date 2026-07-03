"""Tests for ConversationalPlanningEngine."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.conversational_planning_engine import ConversationalPlanningEngine


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
