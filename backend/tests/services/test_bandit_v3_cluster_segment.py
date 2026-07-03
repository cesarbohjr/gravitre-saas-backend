"""Bandit v3 — cluster-segment UCB with v2 fallback."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.learning_strategy_keys import (
    build_cluster_segment_key,
    is_cluster_segment,
    parse_base_segment_key,
    parse_base_segment_key_from_segment,
    parse_segment_key,
)
from app.services.strategy_performance_ledger import (
    MIN_SAMPLES_FOR_PREFERENCE,
    MIN_SAMPLES_FOR_UCB,
    StrategyPerformanceLedger,
)


def test_parse_segment_key_with_cluster():
    classification = {
        "query_cluster_id": "cluster-uuid-1",
        "department": "sales",
        "intent": "question_answering",
    }
    assert parse_segment_key(classification) == "cluster:cluster-uuid-1:sales:question_answering"
    assert parse_base_segment_key(classification) == "sales:question_answering"


def test_parse_base_segment_key_from_cluster_segment():
    segment = "cluster:abc-123:sales:question_answering"
    assert is_cluster_segment(segment)
    assert parse_base_segment_key_from_segment(segment) == "sales:question_answering"


def test_build_cluster_segment_key():
    assert (
        build_cluster_segment_key("id-1", {"intent": "analytics", "department": "ops"})
        == "cluster:id-1:ops:analytics"
    )


@pytest.mark.asyncio
async def test_ledger_v3_selects_cluster_segment_when_evidence():
    ledger = StrategyPerformanceLedger()
    cluster_segment = "cluster:c1:sales:question_answering"
    base_segment = "sales:question_answering"
    ranked_v3 = [
        {
            "strategy_key": "llm:standard",
            "decided_samples": MIN_SAMPLES_FOR_PREFERENCE,
            "win_rate": 0.5,
            "ucb_score": 0.6,
        },
        {
            "strategy_key": "llm:fast",
            "decided_samples": MIN_SAMPLES_FOR_PREFERENCE + 5,
            "win_rate": 0.9,
            "ucb_score": 0.95,
            "weighted_ucb_score": 0.95,
        },
    ]

    async def rank_side_effect(org_id, keys, *, segment_key):
        _ = org_id, keys
        if segment_key == cluster_segment:
            return ranked_v3
        return [{"strategy_key": "llm:standard", "decided_samples": 0, "win_rate": None}]

    with patch.object(ledger, "rank_strategies", AsyncMock(side_effect=rank_side_effect)):
        with patch(
            "app.services.org_learning_profile_service.get_org_learning_profile_service"
        ) as profile_factory:
            profile_factory.return_value.load_profile = AsyncMock(return_value={"segments": {}})
            result = await ledger.choose_preferred_strategy(
                "org-1",
                "llm:standard",
                ["llm:fast", "llm:standard"],
                segment_key=cluster_segment,
                fallback_segment_key=base_segment,
            )

    assert result["bandit_version"] == "v3"
    assert result["selected_key"] == "llm:fast"
    assert result["reason"] == "ledger_win_rate"
    assert result["segment_key_used"] == cluster_segment


@pytest.mark.asyncio
async def test_ledger_v3_falls_back_to_v2_when_cluster_under_gated():
    ledger = StrategyPerformanceLedger()
    cluster_segment = "cluster:c1:default:general"
    base_segment = "default:general"
    ranked_v2 = [
        {
            "strategy_key": "llm:standard",
            "decided_samples": MIN_SAMPLES_FOR_PREFERENCE,
            "win_rate": 0.55,
        },
        {
            "strategy_key": "llm:fast",
            "decided_samples": MIN_SAMPLES_FOR_UCB + 10,
            "win_rate": 0.82,
            "ucb_score": 0.88,
            "weighted_ucb_score": 0.88,
        },
    ]

    async def rank_side_effect(org_id, keys, *, segment_key):
        _ = org_id, keys
        if segment_key == cluster_segment:
            return [
                {"strategy_key": "llm:standard", "decided_samples": 0, "win_rate": None},
                {"strategy_key": "llm:fast", "decided_samples": 1, "win_rate": 1.0, "ucb_score": 0.5},
            ]
        if segment_key == base_segment:
            return ranked_v2
        return []

    with patch.object(ledger, "rank_strategies", AsyncMock(side_effect=rank_side_effect)):
        with patch(
            "app.services.org_learning_profile_service.get_org_learning_profile_service"
        ) as profile_factory:
            profile_factory.return_value.load_profile = AsyncMock(return_value={"segments": {}})
            result = await ledger.choose_preferred_strategy(
                "org-1",
                "llm:standard",
                ["llm:fast", "llm:standard"],
                segment_key=cluster_segment,
                fallback_segment_key=base_segment,
            )

    assert result["bandit_version"] == "v2"
    assert result["fallback_from_segment"] == cluster_segment
    assert result["selected_key"] == "llm:fast"


@pytest.mark.asyncio
async def test_resolve_query_cluster_exact_match():
    from app.services.knowledge_intelligence_service import resolve_query_cluster_for_bandit

    settings = MagicMock()
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {
            "id": "uuid-1",
            "cluster_label": "Billing questions",
            "representative_queries": ["how do i reset my invoice"],
        }
    ]
    with patch(
        "app.services.knowledge_intelligence_service.normalize_query",
        return_value="how do i reset my invoice",
    ):
        match = await resolve_query_cluster_for_bandit(
            settings,
            "org-1",
            "How do I reset my invoice?",
            client=client,
        )
    assert match is not None
    assert match["query_cluster_id"] == "uuid-1"
    assert match["cluster_match_method"] == "exact"


@pytest.mark.asyncio
async def test_enrich_classification_with_query_cluster():
    from app.services.knowledge_intelligence_service import enrich_classification_with_query_cluster

    classification = {"intent": "question_answering", "department": "sales"}
    with patch(
        "app.services.knowledge_intelligence_service.resolve_query_cluster_for_bandit",
        AsyncMock(
            return_value={
                "query_cluster_id": "uuid-9",
                "query_cluster_label": "Pricing",
            }
        ),
    ):
        enriched = await enrich_classification_with_query_cluster(
            classification,
            "org-1",
            "What is our pricing?",
        )
    assert enriched["query_cluster_id"] == "uuid-9"
    assert parse_segment_key(enriched) == "cluster:uuid-9:sales:question_answering"
