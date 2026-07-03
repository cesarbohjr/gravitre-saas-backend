"""Tests for ExplainabilityEngine (Wave 9)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.explainability_engine import ExplainabilityEngine


@pytest.mark.asyncio
async def test_explain_turn_builds_structured_envelope():
    engine = ExplainabilityEngine()
    with patch(
        "app.services.explainability_engine.get_explanation_generator",
    ) as mock_generator:
        mock_generator.return_value.explain = AsyncMock(
            return_value="Answer grounded in org knowledge and recent workflow signals."
        )
        envelope = await engine.explain_turn(
            response_type="answer",
            org_id="org-1",
            sources=[{"title": "Playbook", "score": 0.82}],
            model_output={"answer": "Focus on stalled deals."},
            context_profile={
                "sourcesUsed": [{"label": "Playbook", "type": "rag", "score": 0.82}],
            },
            confidence={"score": 0.78, "missing_context": ["crm_live_data"]},
        )

    assert envelope["summary"]
    assert envelope["evidence"]
    assert envelope["missing_context"] == ["crm_live_data"]
    assert "High confidence" in envelope["confidence_note"]
    assert envelope["advisory_only"] is True


def test_format_user_facing_includes_missing_context():
    engine = ExplainabilityEngine()
    text = engine.format_user_facing(
        {
            "summary": "Based on internal docs.",
            "confidence_note": "Moderate confidence (55%).",
            "missing_context": ["live CRM"],
        }
    )
    assert "Based on internal docs." in text
    assert "Missing context" in text
    assert "Advisory only" in text
