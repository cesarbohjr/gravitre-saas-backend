"""Wave D1+D2 — adaptive learning, learning confidence, and knowledge freshness tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.adaptive_learning_service import AdaptiveLearningService
from app.services.agent_knowledge_assignment_service import AgentKnowledgeAssignmentService
from app.services.ai_trust_layer import get_ai_trust_layer
from app.services.domain_retrieval_policy import RetrievalPlan, apply_source_score
from app.services.knowledge_freshness_service import (
    FRESHNESS_MULTIPLIER_INACCESSIBLE,
    FRESHNESS_MULTIPLIER_STALE,
    KnowledgeFreshnessService,
)
from app.services.learning_confidence_service import LearningConfidenceService


def _settings(**overrides: object) -> MagicMock:
    base = MagicMock(app_env="dev", domain_adaptive_learning_enabled=True)
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_learning_confidence_insufficient_data_in_dev():
    svc = LearningConfidenceService(settings=_settings(app_env="dev"))
    assessment = svc.assess(sample_count=8, positive_count=6, negative_count=1)
    assert assessment.insufficient_data is True
    assert assessment.level == "insufficient_data"
    assert assessment.min_samples_required == 10


def test_learning_confidence_high_with_enough_samples():
    svc = LearningConfidenceService(settings=_settings(app_env="prod"))
    assessment = svc.assess(sample_count=120, positive_count=90, negative_count=20, noise_score=0.1)
    assert assessment.level == "high"
    assert assessment.learning_rate_multiplier > 0.8


def test_learning_confidence_prod_min_samples():
    svc = LearningConfidenceService(settings=_settings(app_env="production"))
    assert svc.min_samples() == 20


def test_freshness_stale_lowers_multiplier():
    svc = KnowledgeFreshnessService()
    assessment = svc.assess_assignment({"id": "a1", "label": "SEO Pack", "freshness_status": "stale"})
    assert assessment.freshness_multiplier == FRESHNESS_MULTIPLIER_STALE
    assert assessment.stale is True
    assert assessment.trust_warning


def test_freshness_inaccessible_excluded_from_retrieval():
    svc = KnowledgeFreshnessService()
    assessment = svc.assess_assignment(
        {
            "id": "a1",
            "label": "CRM",
            "freshness_status": "fresh",
            "permission_valid": False,
        }
    )
    assert assessment.freshness_multiplier == FRESHNESS_MULTIPLIER_INACCESSIBLE
    assert assessment.source_accessible is False


def test_freshness_stale_adds_trust_warning():
    trust = get_ai_trust_layer()
    label, warnings, envelope = trust.build_knowledge_freshness_envelope(
        {
            "freshness_label": "stale_sources_present",
            "freshness_trust_warnings": ["Knowledge source 'SEO Pack' is stale — refresh or revalidate recommended."],
        }
    )
    assert label == "stale_sources_present"
    assert warnings
    adjusted = trust.apply_freshness_to_confidence(0.82, stale_source_warnings=warnings)
    assert adjusted < 0.82
    assert envelope["stale_source_count"] == 1


@pytest.mark.asyncio
async def test_adaptive_learning_org_isolation():
    svc = AdaptiveLearningService(settings=_settings())
    org_a_state = {"sample_count": 50, "positive_count": 40, "negative_count": 5, "adaptive_weight_delta": 1.2}
    org_b_state = {"sample_count": 50, "positive_count": 10, "negative_count": 30, "adaptive_weight_delta": 0.8}

    async def load_side_effect(org_id: str, segment_key: str) -> dict:
        if org_id == "org-a":
            return {**org_a_state, "org_id": org_id, "segment_key": segment_key}
        return {**org_b_state, "org_id": org_id, "segment_key": segment_key}

    with patch.object(svc, "load_segment_state", side_effect=load_side_effect):
        plan_a = await svc.apply_to_retrieval_plan(RetrievalPlan(active=True), "org-a", "default:marketing:seo:qa")
        plan_b = await svc.apply_to_retrieval_plan(RetrievalPlan(active=True), "org-b", "default:marketing:seo:qa")
    assert plan_a.adaptive_weight_delta == 1.2
    assert plan_b.adaptive_weight_delta == 0.8


@pytest.mark.asyncio
async def test_adaptive_learning_segment_isolation():
    svc = AdaptiveLearningService(settings=_settings())

    async def load_side_effect(org_id: str, segment_key: str) -> dict:
        if segment_key.endswith(":marketing:seo:qa"):
            return {
                "sample_count": 40,
                "positive_count": 30,
                "negative_count": 5,
                "adaptive_weight_delta": 1.15,
                "outcome_multiplier": 1.1,
                "assignment_boost_deltas": {"a1": 1.1},
            }
        return {
            "sample_count": 40,
            "positive_count": 5,
            "negative_count": 25,
            "adaptive_weight_delta": 0.85,
            "outcome_multiplier": 0.9,
            "assignment_boost_deltas": {"a1": 0.9},
        }

    with patch.object(svc, "load_segment_state", side_effect=load_side_effect):
        marketing = await svc.apply_to_retrieval_plan(
            RetrievalPlan(active=True, assignment_boosts={"a1": 1.0}),
            "org-1",
            "default:marketing:seo:qa",
        )
        sales = await svc.apply_to_retrieval_plan(
            RetrievalPlan(active=True, assignment_boosts={"a1": 1.0}),
            "org-1",
            "default:sales:forecasting:qa",
        )
    assert marketing.adaptive_weight_delta > sales.adaptive_weight_delta
    assert marketing.assignment_boosts["a1"] > sales.assignment_boosts["a1"]


@pytest.mark.asyncio
async def test_positive_outcome_increases_weight():
    svc = AdaptiveLearningService(settings=_settings())
    with patch.object(svc, "load_segment_state", return_value=svc._default_state("org-1", "seg")):
        with patch.object(svc, "_persist_state", new_callable=AsyncMock) as persist:
            result = await svc.ingest_response_outcome(
                "org-1",
                segment_key="default:marketing:seo:qa",
                response={"retrieval_effectiveness": {"retrieval_score": 0.9, "assignment_ids_used": ["a1"]}},
                polarity="positive",
            )
    assert result["status"] == "insufficient_data"
    persist.assert_called_once()
    saved = persist.call_args[0][2]
    assert saved["sample_count"] == 1

    state = svc._default_state("org-1", "seg")
    state.update({"sample_count": 15, "positive_count": 12, "negative_count": 2, "noise_score": 0.1})
    with patch.object(svc, "load_segment_state", return_value=state):
        with patch.object(svc, "_persist_state", new_callable=AsyncMock) as persist:
            result = await svc.ingest_response_outcome(
                "org-1",
                segment_key="default:marketing:seo:qa",
                response={"retrieval_effectiveness": {"retrieval_score": 0.9, "assignment_ids_used": ["a1"]}},
                polarity="positive",
            )
    assert result["status"] == "updated"
    saved = persist.call_args[0][2]
    assert float(saved["outcome_multiplier"]) > 1.0
    assert float(saved["adaptive_weight_delta"]) > 1.0


@pytest.mark.asyncio
async def test_negative_outcome_decreases_weight():
    svc = AdaptiveLearningService(settings=_settings())
    state = svc._default_state("org-1", "seg")
    state.update({"sample_count": 15, "positive_count": 5, "negative_count": 8, "noise_score": 0.1})
    with patch.object(svc, "load_segment_state", return_value=state):
        with patch.object(svc, "_persist_state", new_callable=AsyncMock) as persist:
            await svc.ingest_response_outcome(
                "org-1",
                segment_key="default:marketing:seo:qa",
                response={"retrieval_effectiveness": {"retrieval_score": 0.2, "assignment_ids_used": ["a1"]}},
                polarity="negative",
            )
    saved = persist.call_args[0][2]
    assert float(saved["outcome_multiplier"]) < 1.0
    assert float(saved["adaptive_weight_delta"]) < 1.0


@pytest.mark.asyncio
async def test_noisy_feedback_smaller_learning_step():
    svc = AdaptiveLearningService(settings=_settings())
    state = svc._default_state("org-1", "seg")
    state.update({"sample_count": 15, "positive_count": 10, "negative_count": 3, "noise_score": 0.1})
    clean_state = dict(state)

    with patch.object(svc, "load_segment_state", return_value=state):
        with patch.object(svc, "_persist_state", new_callable=AsyncMock) as persist_noisy:
            await svc.ingest_response_outcome(
                "org-1",
                segment_key="seg",
                response={"retrieval_effectiveness": {"retrieval_score": 0.9}},
                polarity="positive",
                signal_weight=0.4,
            )
    noisy_delta = float(persist_noisy.call_args[0][2]["adaptive_weight_delta"])

    with patch.object(svc, "load_segment_state", return_value=clean_state):
        with patch.object(svc, "_persist_state", new_callable=AsyncMock) as persist_clean:
            await svc.ingest_response_outcome(
                "org-1",
                segment_key="seg",
                response={"retrieval_effectiveness": {"retrieval_score": 0.9}},
                polarity="positive",
                signal_weight=1.0,
            )
    clean_delta = float(persist_clean.call_args[0][2]["adaptive_weight_delta"])
    assert (clean_delta - 1.0) > (noisy_delta - 1.0)


@pytest.mark.asyncio
async def test_insufficient_data_preserves_default_multipliers():
    svc = AdaptiveLearningService(settings=_settings())
    with patch.object(svc, "load_segment_state", return_value=svc._default_state("org-1", "seg")):
        plan = await svc.apply_to_retrieval_plan(RetrievalPlan(active=True), "org-1", "seg")
    assert plan.insufficient_data is True
    assert plan.adaptive_weight_delta == 1.0
    assert plan.outcome_multiplier == 1.0


def test_wave_c_preserved_when_adaptive_disabled():
    plan = RetrievalPlan(active=True)
    score = apply_source_score(0.8, {"metadata": {}}, plan, match_tier="unassigned")
    assert score == pytest.approx(0.8 * 0.65)


def test_inaccessible_assignment_filtered_from_scored_results():
    service = AgentKnowledgeAssignmentService(settings=MagicMock())
    plan = RetrievalPlan(active=True, assignment_freshness_multipliers={"a1": 0.0})
    assignments = [{"id": "a1", "source_id": "x", "label": "Blocked", "enabled": True}]
    sources = [{"metadata": {"assignment_id": "a1"}, "score": 0.9, "title": "Blocked doc"}]
    scored, _ = service.apply_retrieval_scoring(sources, assignments, plan=plan)
    assert scored == []


def test_stale_freshness_reduces_retrieval_score():
    plan = RetrievalPlan(active=True, assignment_freshness_multipliers={"a1": FRESHNESS_MULTIPLIER_STALE})
    source = {"metadata": {"assignment_id": "a1"}, "score": 1.0}
    score = apply_source_score(1.0, source, plan, match_tier="assignment_id")
    assert score < 1.0


@pytest.mark.asyncio
async def test_adaptive_learning_disabled_skips_ingest():
    svc = AdaptiveLearningService(settings=_settings(domain_adaptive_learning_enabled=False))
    result = await svc.ingest_response_outcome("org-1", segment_key="seg")
    assert result["status"] == "disabled"
