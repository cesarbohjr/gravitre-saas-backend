"""Tests for AdvisorModeEngine (Wave 5)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.advisor_mode_engine import AdvisorModeEngine


@pytest.mark.asyncio
async def test_generate_brief_merges_signals_and_decision_recs():
    engine = AdvisorModeEngine(settings=MagicMock())
    engine._signals.collect_signals = AsyncMock(
        return_value={
            "signals": [
                {
                    "id": "sig-1",
                    "title": "Pipeline stalled",
                    "summary": "12 deals inactive",
                    "signal_type": "risk",
                    "quality_score": 0.8,
                    "source": "predictions",
                }
            ]
        }
    )
    engine._signals.generate_department_brief = AsyncMock(
        return_value={
            "what_changed": ["Deal velocity dropped"],
            "confidence": 0.7,
            "evidence": [{"source": "workflows", "title": "Stale deals"}],
        }
    )
    engine._quality.filter_advisor_actions = AsyncMock(
        side_effect=lambda _org, actions, **kwargs: actions
    )
    engine._decision.recommend_next_action = AsyncMock(
        return_value={
            "recommendations": [
                {
                    "id": "rec-1",
                    "action": "Review top stalled deals",
                    "reasoning": "High-value pipeline risk",
                    "confidence": 0.75,
                }
            ]
        }
    )
    engine._user_intel.get_daily_briefing = AsyncMock(
        return_value={"bullets": [{"text": "3 workflows failed overnight"}]}
    )

    brief = await engine.generate_brief(
        "org-1",
        "user-1",
        department="sales",
        query="What should sales focus on?",
        client=MagicMock(),
    )

    assert brief["mode"] == "advisor"
    assert brief["department"] == "sales"
    assert brief["advisory_only"] is True
    assert any("Pipeline stalled" in str(row.get("action") or row.get("title")) for row in brief["recommended_actions"])
    assert brief["risks"]
    assert "what_changed" in brief


@pytest.mark.asyncio
async def test_generate_executive_brief_aggregates_departments():
    engine = AdvisorModeEngine(settings=MagicMock())
    engine._signals.generate_executive_brief = AsyncMock(
        return_value={
            "title": "Executive brief",
            "top_risks": [{"title": "Connector drift"}],
            "departments": [
                {
                    "department": "operations",
                    "what_changed": ["Workflow backlog grew"],
                    "recommended_actions": [{"action": "Clear failed runs", "confidence": 0.6}],
                }
            ],
        }
    )
    engine._quality.filter_advisor_actions = AsyncMock(
        side_effect=lambda _org, actions, **kwargs: actions
    )
    engine._research.generate_executive_brief = AsyncMock(return_value={"summary": "Cross-org health stable"})

    brief = await engine.generate_executive_brief("org-1", "user-1", client=MagicMock())

    assert brief["mode"] == "advisor_executive"
    assert brief["research_summary"] == "Cross-org health stable"
    assert brief["recommended_actions"]


def test_format_brief_section_includes_advisory_disclaimer():
    engine = AdvisorModeEngine(settings=MagicMock())
    text = engine.format_brief_section(
        {
            "department": "sales",
            "what_changed": ["Pipeline update"],
            "why": "Risk signals detected.",
            "recommended_actions": [{"action": "Follow up", "reason": "Stale deals"}],
            "confidence": 0.72,
        }
    )
    assert "Advisor brief" in text
    assert "advisory only" in text.lower()
