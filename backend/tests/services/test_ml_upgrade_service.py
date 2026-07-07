"""Tests for ML upgrade orchestrator."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.hybrid_memory_service import HybridMemoryService
from app.services.ml_upgrade_service import MLUpgradeService


def test_hybrid_memory_fuse_with_rag_sources():
    service = HybridMemoryService()
    rag = [{"id": "rag-1", "content": "policy doc", "score": 0.9, "source": "kb"}]
    hybrid = [{"id": "memory:1", "content": "remember this", "score": 0.8, "source": "agent_memory", "kind": "memory"}]
    merged = service.fuse_with_rag_sources(rag, hybrid, top_k=5)
    assert merged
    assert any(row.get("id") == "rag-1" for row in merged)
    assert any(str(row.get("id", "")).startswith("memory:") for row in merged)


@pytest.mark.asyncio
async def test_ml_upgrade_org_adaptive_learning_waits_without_outcomes():
    service = MLUpgradeService(settings=MagicMock(domain_adaptive_learning_enabled=False))
    with patch.object(service, "_count_outcome_events", AsyncMock(return_value=10)):
        result = await service.upgrade_org_adaptive_learning("org-1")
    assert result["status"] == "waiting"


@pytest.mark.asyncio
async def test_ml_upgrade_provider_ab_routing():
    service = MLUpgradeService()
    result = await service.upgrade_provider_ab_routing("org-1")
    assert result["status"] == "live"
    assert "provider:openai" in result["provider_candidates"]
