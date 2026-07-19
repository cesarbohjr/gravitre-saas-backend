"""Module C / STA-331 — hardcoded confidence must be labeled or computed."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_MODEL_SELECTION,
    computed_confidence,
    estimated_confidence,
    label_confidence,
    model_selection_ml_confidence,
)
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.meson_service import MesonInterpretResult, MesonSuggestion, _rank_suggestions_by_feedback
from app.services.recommendation_heuristics_service import build_heuristic_recommendations


def test_label_confidence_is_canonical_helper():
    labeled = label_confidence(0.65, source=CONFIDENCE_SOURCE_MODEL_SELECTION, is_estimate=True)
    assert labeled["confidence"] == 0.65
    assert labeled["confidence_is_estimate"] is True
    assert labeled["confidenceIsEstimate"] is True
    assert labeled["confidence_source"] == CONFIDENCE_SOURCE_MODEL_SELECTION
    missing = label_confidence(None, source="insufficient_data")
    assert missing["confidence"] is None
    assert missing["confidence_source"] == "insufficient_data"


def test_estimated_vs_computed_helpers():
    est = estimated_confidence(0.8)
    assert est["confidence_is_estimate"] is True
    assert est["confidence_source"] == "heuristic"
    real = computed_confidence(0.9, source="feedback_acceptance_rate")
    assert real["confidence_is_estimate"] is False
    assert real["confidence_source"] == "feedback_acceptance_rate"


def test_model_selection_ml_confidence_is_labeled_estimate():
    high = model_selection_ml_confidence("ml_internal")
    low = model_selection_ml_confidence("llm")
    assert high["confidence"] == 0.65
    assert low["confidence"] == 0.45
    assert high["confidence_is_estimate"] is True
    assert high["confidence_source"] == CONFIDENCE_SOURCE_MODEL_SELECTION


def test_meson_interpret_defaults_to_estimate():
    result = MesonInterpretResult(
        intent="build a sales agent",
        department="sales",
        systems=["crm"],
        outputTypes=["workflows"],
        generatedConfig={
            "agent": "Sales Agent",
            "agent_role": "Specialist",
            "agent_description": "x",
            "training": [],
            "workflows": [],
            "sample_outputs": [],
        },
        confidence=0.55,
    )
    assert result.confidence_is_estimate is True
    assert result.confidence_source == "heuristic"


def test_heuristic_recommendation_cards_mark_confidence_estimate():
    payload = build_heuristic_recommendations(
        connected_connectors=[
            {"vendor": "zendesk", "label": "Zendesk", "status": "connected", "executable": False},
            {"vendor": "slack", "label": "Slack", "status": "connected", "executable": True},
        ],
        usage_by_connector={},
        installed_packs=set(),
    )
    assert payload["recommendations"]
    for card in payload["recommendations"]:
        assert card["confidenceIsEstimate"] is True
        assert card["confidence_is_estimate"] is True
        assert card["confidenceSource"] == "heuristic"


def test_meson_suggestions_default_to_estimate():
    suggestion = MesonSuggestion(
        id="add-approval",
        nodeType="approval",
        label="Quality Gate",
        reason="Add approval?",
        confidence=0.82,
    )
    assert suggestion.confidence_is_estimate is True
    assert suggestion.confidence_source == "heuristic"


def test_meson_feedback_computes_real_confidence():
    suggestions = [
        MesonSuggestion(
            id="add-approval",
            nodeType="approval",
            label="Quality Gate",
            confidence=0.82,
        )
    ]
    ranked = _rank_suggestions_by_feedback(
        suggestions,
        {"by_suggestion": {"add-approval": {"accepted": 3, "dismissed": 1}}},
    )
    assert ranked
    assert ranked[0].confidence_is_estimate is False
    assert ranked[0].confidence_source == "feedback_acceptance_rate"
    assert ranked[0].confidence == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_kg_relationship_score_is_estimate_prior():
    service = KnowledgeGraphService()
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(
        data=[
            {
                "confidence": 0.5,
                "evidence_count": 2,
                "relationship_type": "tracked-by",
                "last_observed_at": None,
            }
        ]
    )
    with patch.object(service, "_client", return_value=client):
        result = await service.score_relationship("org-1", "a", "b", client=client)
    assert isinstance(result, dict)
    assert result["confidence_is_estimate"] is True
    assert result["confidence_source"] == "type_reliability_prior"
    assert result["confidence"] > 0
    assert "both estimates" in (result.get("note") or "").lower()


@pytest.mark.asyncio
async def test_admin_chat_health_no_fake_065_fallback():
    from app.routers import admin_chat

    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.gte.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(data=[])

    with (
        patch("app.routers.admin_chat.get_supabase_client", return_value=client),
        patch("app.routers.admin_chat.get_settings", return_value=MagicMock()),
    ):
        result = await admin_chat.get_conversation_health(
            org_id="org-1",
            _admin=("u1", "admin"),
            settings=MagicMock(),
        )
    assert result["avg_confidence_7d"] is None
    assert result["confidence_source"] == "insufficient_data"
    assert result["quality_sample_size"] == 0
