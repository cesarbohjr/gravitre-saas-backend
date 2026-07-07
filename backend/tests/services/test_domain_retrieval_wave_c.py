"""Wave C1+C2 — domain retrieval policy and assignment alignment tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agent_knowledge_assignment_service import AgentKnowledgeAssignmentService
from app.services.domain_retrieval_policy import (
    RetrievalPlan,
    apply_source_score,
    build_retrieval_plan,
    should_fetch_graph,
)
from app.services.retrieval_provenance import build_from_rag_row, summarize_retrieval_effectiveness


def _domain_classification(**overrides: object) -> dict:
    base = {
        "intent": "question_answering",
        "domain": {
            "department_key": "marketing",
            "subdomain_key": "seo",
            "confidence": 0.82,
            "routing_active": True,
            "profile_id": "marketing",
        },
    }
    base.update(overrides)
    return base


def test_retrieval_plan_inactive_when_flag_disabled():
    settings = MagicMock(domain_retrieval_policy_enabled=False)
    plan = build_retrieval_plan(_domain_classification(), [], settings=settings)
    assert plan.active is False


def test_retrieval_plan_active_for_marketing_seo():
    settings = MagicMock(domain_retrieval_policy_enabled=True)
    plan = build_retrieval_plan(_domain_classification(), [], settings=settings)
    assert plan.active is True
    assert plan.domain_department == "marketing"
    assert plan.domain_subdomain == "seo"
    assert plan.source_type_weights["rag"] >= 0.85
    assert plan.graph_weight <= 0.45


def test_retrieval_plan_sales_graph_weight():
    settings = MagicMock(domain_retrieval_policy_enabled=True)
    classification = _domain_classification(
        domain={
            "department_key": "sales",
            "subdomain_key": "forecasting",
            "confidence": 0.9,
            "routing_active": True,
            "profile_id": "sales",
        }
    )
    plan = build_retrieval_plan(classification, [], settings=settings)
    assert plan.graph_weight >= 0.9
    assert should_fetch_graph(classification, plan) is True


def test_assignment_match_priority_assignment_id():
    service = AgentKnowledgeAssignmentService(settings=MagicMock())
    assignments = [{"id": "a1", "source_id": "folder-1", "label": "Brand", "enabled": True}]
    source = {"metadata": {"assignment_id": "a1"}, "score": 0.8}
    assert service.classify_source_match(source, assignments) == "assignment_id"


def test_assignment_match_department_subdomain():
    service = AgentKnowledgeAssignmentService(settings=MagicMock())
    plan = RetrievalPlan(active=True, domain_department="marketing", domain_subdomain="seo")
    assignments = [{"id": "a1", "department": "marketing", "subdomain": "seo", "label": "SEO", "enabled": True}]
    source = {"metadata": {"department": "marketing"}, "score": 0.7}
    assert service.classify_source_match(source, assignments, plan=plan) == "department_subdomain"


def test_unassigned_sources_kept_when_not_strict():
    service = AgentKnowledgeAssignmentService(settings=MagicMock())
    plan = RetrievalPlan(active=True, strict_assignment_mode=False, allow_unassigned_with_lower_confidence=True)
    assignments = [{"id": "a1", "source_id": "x", "label": "Assigned", "enabled": True}]
    sources = [{"metadata": {}, "score": 0.5, "title": "Org doc"}]
    scored, _ = service.apply_retrieval_scoring(sources, assignments, plan=plan)
    assert len(scored) == 1
    assert scored[0]["match_tier"] == "unassigned"


def test_strict_assignment_mode_filters_unmatched():
    service = AgentKnowledgeAssignmentService(settings=MagicMock())
    plan = RetrievalPlan(active=True, strict_assignment_mode=True)
    assignments = [{"id": "a1", "source_id": "x", "label": "Assigned", "enabled": True}]
    sources = [{"metadata": {}, "score": 0.5, "title": "Org doc"}]
    scored, missing = service.apply_retrieval_scoring(sources, assignments, plan=plan)
    assert scored == []
    assert missing


def test_provenance_envelope_on_rag_row():
    row = {"title": "Playbook", "score": 0.77, "metadata": {"assignment_id": "a1", "source_type": "hubspot_view"}}
    envelope = build_from_rag_row(row, plan=RetrievalPlan(active=True, domain_department="sales"), match_tier="assignment_id")
    assert envelope["source_name"] == "Playbook"
    assert envelope["assignment_id"] == "a1"
    assert envelope["retrieval_policy"] == "domain_v1"


def test_retrieval_effectiveness_summary():
    sources = [
        {"score": 0.8, "provenance": {"source_name": "CRM", "assignment_id": "a1", "match_tier": "assignment_id"}},
    ]
    summary = summarize_retrieval_effectiveness(
        sources,
        plan=RetrievalPlan(active=True),
        classification=_domain_classification(),
    )
    assert summary["assignment_ids_used"] == ["a1"]
    assert summary["retrieval_score"] == 0.8


def test_apply_source_score_unassigned_penalty():
    plan = RetrievalPlan(active=True)
    score = apply_source_score(0.8, {"metadata": {}}, plan, match_tier="unassigned")
    assert score < 0.8


def test_intelligence_pack_catalog_has_four_packs():
    from app.marketplace.intelligence_packs.catalog import list_intelligence_pack_specs

    specs = list_intelligence_pack_specs()
    assert len(specs) == 4
    assert {spec.pack_id for spec in specs} == {
        "marketing-intelligence-pack",
        "sales-intelligence-pack",
        "support-intelligence-pack",
        "msp-intelligence-pack",
    }


def test_future_proof_retrieval_plan_fields():
    plan = RetrievalPlan(
        active=True,
        adaptive_weight_delta=1.1,
        meta_learning_delta=1.05,
        outcome_multiplier=1.1,
        optimization_multiplier=1.0,
    )
    assert plan.learning_multiplier() == pytest.approx(1.1 * 1.05 * 1.1 * 1.0)


def test_apply_source_score_multiplicative_learning():
    plan = RetrievalPlan(
        active=True,
        adaptive_weight_delta=1.1,
        outcome_multiplier=1.1,
        assignment_freshness_multipliers={"a1": 0.85},
        assignment_boosts={"a1": 1.2},
    )
    source = {"metadata": {"assignment_id": "a1"}, "score": 1.0}
    score = apply_source_score(1.0, source, plan, match_tier="assignment_id")
    expected = 1.0 * 1.2 * 0.85 * 1.1 * 1.1
    assert score == pytest.approx(round(expected, 6))


def test_inaccessible_source_scores_zero():
    plan = RetrievalPlan(active=True, assignment_freshness_multipliers={"a1": 0.0})
    source = {"metadata": {"assignment_id": "a1"}, "score": 0.9}
    assert apply_source_score(0.9, source, plan, match_tier="assignment_id") == 0.0


@pytest.mark.asyncio
async def test_context_assembler_delegates_to_unified_retrieval():
    from app.services.context_assembler import ContextAssembler

    assembler = ContextAssembler(settings=MagicMock())
    bundle = MagicMock()
    bundle.rag_sources = [{"content": "hello", "score": 0.9, "provenance": {}}]
    bundle.memory_context = {}
    bundle.graph_context = {}
    bundle.retrieval_plan = {"active": True}
    bundle.retrieval_effectiveness = {"retrieval_score": 0.9}
    bundle.sources = []
    with patch("app.services.context_assembler.get_unified_retrieval_service") as factory:
        factory.return_value.retrieve = AsyncMock(return_value=bundle)
        with patch(
            "app.services.context_assembler.get_company_intelligence_orchestrator"
        ) as company_factory:
            company_factory.return_value.get_context_for_prompt = AsyncMock(return_value="company")
            result = await assembler.assemble(
                "org-1",
                "user-1",
                "SEO question",
                _domain_classification(),
                client=MagicMock(),
            )
    assert result["retrieval_plan"]["active"] is True
    assert result["retrieval_effectiveness"]["retrieval_score"] == 0.9
    assert result["rag_context"]
