"""Phase E: long-horizon ledger v2 and memory conflict surfacing."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.ml.federated_learning import FederatedLearningCoordinator
from app.ml.model_catalog import GRAVITRE_ML_CATALOG
from app.ml.base import ModelStatus
from app.services.agent_memory_service import detect_agent_memory_conflicts
from app.services.strategy_performance_ledger import StrategyPerformanceLedger, _ucb_score


def test_federated_learning_remains_disabled_in_catalog():
    assert GRAVITRE_ML_CATALOG["federated_learning"]["status"] == ModelStatus.DISABLED


@pytest.mark.asyncio
async def test_federated_coordinator_returns_disabled():
    result = await FederatedLearningCoordinator().predict_structured()
    assert result["status"] == "disabled"


def test_ucb_score_prefers_explored_arms():
    assert _ucb_score(8, 2, 20) > _ucb_score(2, 8, 20)


@pytest.mark.asyncio
async def test_ledger_v2_can_select_ucb_candidate():
    ledger = StrategyPerformanceLedger()
    ranked = [
        {
            "strategy_key": "llm:standard",
            "decided_samples": 25,
            "wins": 12,
            "losses": 13,
            "win_rate": 0.48,
            "ucb_score": 0.55,
            "sample_size": 25,
        },
        {
            "strategy_key": "llm:fast",
            "decided_samples": 30,
            "wins": 22,
            "losses": 8,
            "win_rate": 0.73,
            "ucb_score": 0.91,
            "sample_size": 30,
        },
    ]
    with patch.object(ledger, "rank_strategies", AsyncMock(return_value=ranked)):
        ranked[0]["weighted_ucb_score"] = 0.55
        ranked[1]["weighted_ucb_score"] = 0.91
        with patch(
            "app.services.org_learning_profile_service.get_org_learning_profile_service"
        ) as profile_factory:
            profile_factory.return_value.load_profile = AsyncMock(return_value={"segments": {}})
            result = await ledger.choose_preferred_strategy(
                "org-1",
                "llm:standard",
                ["llm:fast", "llm:standard"],
            )
    assert result["bandit_version"] == "v2"
    assert result["selected_key"] in {"llm:standard", "llm:fast"}


def test_agent_memory_conflict_detection():
    memories = [
        {"id": "1", "content": "The deployment was approved by leadership", "category": "fact"},
        {"id": "2", "content": "The deployment was rejected by leadership", "category": "fact"},
    ]
    conflicts = detect_agent_memory_conflicts(memories)
    assert len(conflicts) >= 1
    assert conflicts[0]["requires_human_review"] is True
