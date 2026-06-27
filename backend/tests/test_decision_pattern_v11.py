from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.memory_promotion_service import MemoryPromotionService, MemoryPromotionStatus


@pytest.mark.asyncio
async def test_pattern_requires_minimum_sample_size():
    service = MemoryPromotionService(settings=MagicMock())
    decisions = [{"type": "workflow", "priority": "high", "status": "approved"}] * 10
    with patch.object(service, "_load_recent_decisions", new=AsyncMock(return_value=decisions)):
        created = await service.detect_decision_pattern_candidates("org-1")
    assert created == []


@pytest.mark.asyncio
async def test_detected_pattern_uses_only_confirmed_structured_fields():
    service = MemoryPromotionService(settings=MagicMock())
    decisions = [{"type": "workflow", "priority": "high", "status": "approved", "context": {}}] * 16
    patterns = service._detect_threshold_patterns(decisions)
    assert patterns
    assert patterns[0]["evidence"]["field"] in {"type", "priority"}
    assert "amount" not in str(patterns[0]["evidence"])


@pytest.mark.asyncio
async def test_decision_pattern_always_pending_approval():
    service = MemoryPromotionService(settings=MagicMock())
    decisions = [{"type": "workflow", "priority": "high", "status": "approved", "context": {}}] * 16
    with patch.object(service, "_load_recent_decisions", new=AsyncMock(return_value=decisions)):
        with patch.object(service, "_client", return_value=MagicMock()):
            with patch.object(
                service,
                "_upsert_candidate",
                return_value={"status": MemoryPromotionStatus.PENDING_APPROVAL.value},
            ) as upsert:
                created = await service.detect_decision_pattern_candidates("org-1")
    assert created
    assert upsert.call_args.kwargs["status"] == MemoryPromotionStatus.PENDING_APPROVAL.value
    assert upsert.call_args.kwargs["candidate_type"] == "decision_pattern"


@pytest.mark.asyncio
async def test_reuses_existing_orchestrator_schedule():
    import app.schedulers.memory_promotion_scheduler as scheduler_module

    source = open(scheduler_module.__file__, encoding="utf-8").read()
    assert "run_evaluation" in source
    assert "outcome_scheduler" not in source.lower()
    assert "decision_pattern_scheduler" not in source.lower()


def test_no_new_memory_storage_system_introduced():
    import app.services.memory_promotion_service as module

    source = open(module.__file__, encoding="utf-8").read()
    assert "detect_decision_pattern_candidates" in source
    assert "agent_memories" in source
    assert "decision_memories" not in source
