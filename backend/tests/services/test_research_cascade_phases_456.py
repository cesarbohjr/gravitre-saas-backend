"""Tests for adaptive research cascade Phases 4–6."""
from __future__ import annotations

from app.services.adaptive_research_cascade import (
    build_cascade_stage_progress,
    build_research_progress_steps,
    confidence_band_from_score,
    enrich_research_cascade,
    should_emit_research_cascade_sse,
)
from app.services.research_action_bridge import (
    attach_research_actions_to_cascade,
    build_research_pending_task,
    suggest_research_actions,
)


def test_confidence_band_from_real_scores():
    assert confidence_band_from_score(0.82) == "high"
    assert confidence_band_from_score(0.55) == "medium"
    assert confidence_band_from_score(0.2) == "low"
    assert confidence_band_from_score(None) == "unknown"


def test_enrich_research_cascade_adds_source_breakdown():
    cascade = enrich_research_cascade(
        {"active_stages": ["internal_rag", "reasoning"], "research_scope": "internal_only"},
        retrieval_effectiveness={
            "retrieval_score": 0.61,
            "source_count": 3,
            "top_sources": [{"source_name": "Policy", "score": 0.61, "source_type": "rag_chunk"}],
        },
        sources=[
            {"kind": "knowledge", "score": 0.61},
            {"kind": "memory", "score": 0.4},
            {"kind": "internet", "score": 0.55},
        ],
    )
    assert cascade["confidence_band"] == "medium"
    assert cascade["source_breakdown"]["knowledge"] == 1
    assert cascade["source_breakdown"]["internet"] == 1
    assert cascade["stage_progress"]
    assert cascade["progress_steps"]


def test_build_cascade_stage_progress_marks_internet_and_packs():
    stages = build_cascade_stage_progress(
        {
            "active_stages": ["internal_rag", "intelligence_packs", "internet_research", "reasoning"],
            "internet_research_enabled": True,
            "internet_research": {"ran": True, "result_count": 2},
            "intelligence_packs": {"ran": True, "result_count": 1},
        }
    )
    by_stage = {row["stage"]: row for row in stages}
    assert by_stage["internet_research"]["status"] == "completed"
    assert by_stage["intelligence_packs"]["status"] == "completed"
    assert by_stage["reasoning"]["status"] == "pending"


def test_should_emit_research_cascade_sse_for_broad_scope():
    assert should_emit_research_cascade_sse({"research_scope": "everything", "active_stages": ["internal_rag"]})
    assert should_emit_research_cascade_sse(
        {
            "internal_thin": True,
            "internet_research_enabled": True,
            "active_stages": ["internal_rag", "internet_research"],
        }
    )
    assert not should_emit_research_cascade_sse(None)


def test_suggest_research_actions_requires_action_intent():
    cascade = {"research_scope": "everything", "suggest_broaden": False}
    assert not suggest_research_actions(
        "What is our refund policy?",
        research_cascade=cascade,
        connected_integrations=["hubspot"],
    )
    actions = suggest_research_actions(
        "Create a HubSpot contact from this research",
        research_cascade=cascade,
        connected_integrations=["hubspot"],
    )
    assert actions
    assert actions[0]["integration"] == "hubspot"
    assert "requires_approval" in actions[0]


def test_attach_research_actions_and_pending_task():
    action = {
        "invoke_action": "apollo.lists.create",
        "integration": "apollo",
        "label": "Create Apollo list",
        "requires_approval": True,
    }
    merged = attach_research_actions_to_cascade({}, [action])
    assert merged["has_gated_actions"] is True
    pending = build_research_pending_task(action)
    assert pending["type"] == "connector_action"
    assert pending["status"] == "awaiting_confirm"
    assert pending["params"]["research_suggested"] is True


def test_build_research_progress_steps_readable():
    steps = build_research_progress_steps(
        {
            "active_stages": ["internal_rag", "internet_research"],
            "internet_research_enabled": False,
            "internet_research": {"ran": False},
        }
    )
    assert any("Searching internal knowledge" in step for step in steps)
    assert any("Searching the web" in step for step in steps)
