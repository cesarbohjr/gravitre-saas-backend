"""Tests for Research Manager — confidence-gated cascade decisions."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.research_manager import (
    CascadeStage,
    authority_rank_sources,
    build_cascade_plan,
    compress_evidence_section,
    is_confidence_sufficient,
    should_fetch_graph_layer,
)


def test_is_confidence_sufficient_strong_internal():
    assert is_confidence_sufficient(
        retrieval_effectiveness={"source_count": 5, "retrieval_score": 0.82},
        rag_sources=[{"content": "Policy section 4", "score": 0.9}],
    )


def test_is_confidence_sufficient_rejects_thin():
    assert not is_confidence_sufficient(
        retrieval_effectiveness={"source_count": 1, "retrieval_score": 0.4},
        rag_sources=[{"content": "one hit", "score": 0.4}],
    )


def test_build_cascade_plan_stops_external_when_confident():
    plan = build_cascade_plan(
        research_scope=None,
        settings=SimpleNamespace(internet_research_enabled=False, tavily_api_key=""),
        knowledge_assignments=[],
        confidence_sufficient=True,
        stopped_at=CascadeStage.INTERNAL_RAG.value,
    )
    assert plan.skip_external is True
    assert plan.confidence_sufficient is True
    assert CascadeStage.INTERNET_RESEARCH.value not in plan.stages_to_run


def test_build_cascade_plan_keeps_external_when_user_scoped_and_thin():
    plan = build_cascade_plan(
        research_scope="intelligence_packs",
        settings=SimpleNamespace(internet_research_enabled=False, tavily_api_key=""),
        knowledge_assignments=[{"metadata": {"intelligence_pack_id": "executive-intelligence-pack"}}],
        confidence_sufficient=False,
    )
    assert plan.skip_external is False
    assert CascadeStage.INTELLIGENCE_PACKS.value in plan.stages_to_run


def test_should_fetch_graph_layer_skips_when_confident():
    assert not should_fetch_graph_layer(
        classification={},
        plan_active=True,
        requires_graph=False,
        graph_weight=0.95,
        confidence_sufficient=True,
    )


def test_should_fetch_graph_layer_honors_requires_graph():
    assert should_fetch_graph_layer(
        classification={"requires_graph": True},
        plan_active=False,
        requires_graph=True,
        graph_weight=0.0,
        confidence_sufficient=False,
    )


def test_authority_rank_deduplicates_and_orders_knowledge_first():
    rows = authority_rank_sources(
        [
            {"kind": "internet", "content": "web snippet", "score": 0.99, "id": "w1"},
            {"kind": "knowledge", "content": "web snippet", "score": 0.7, "id": "k1"},
            {"kind": "knowledge", "content": "internal doc", "score": 0.8, "id": "k2"},
        ]
    )
    assert len(rows) == 2
    assert rows[0]["kind"] == "knowledge"
    assert rows[0]["id"] == "k2"


def test_compress_evidence_section_bounded():
    section = compress_evidence_section(
        [{"source": "KB", "content": "x" * 2000, "score": 0.9, "kind": "knowledge"}],
        per_source_chars=100,
    )
    assert section.startswith("<knowledge_base>")
    assert len(section) < 500
