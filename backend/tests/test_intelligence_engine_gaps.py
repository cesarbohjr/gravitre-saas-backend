"""Tests for Gravitre Intelligence Engine gap-closure modules."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.agent_intelligence import AgentIntelligence
from app.operators.assistant_mode_config import MODE_CONFIG
from app.services.answer_explanation import generate_answer_explanation
from app.services.answer_validator import SAFE_FALLBACK, validate_grounded_answer
from app.services.context_conflict_detection import dedupe_chunks, detect_chunk_conflicts
from app.services.query_rewriter import rewrite_for_retrieval
from app.services.sync_confidence import compute_sync_confidence


@pytest.mark.asyncio
async def test_query_rewriter_preserves_intent():
    result = await rewrite_for_retrieval("pipeline status", None)
    assert result["original_query"] == "pipeline status"
    assert result["refined_query"] == "pipeline status"


@pytest.mark.asyncio
async def test_query_rewriter_uses_conversation_context():
    router = MagicMock()
    router.complete = AsyncMock(
        return_value=SimpleNamespace(content='{"refined_query": "Q4 revenue forecast for Acme Corp"}')
    )
    history = [
        {"role": "user", "content": "Tell me about Acme Corp"},
        {"role": "assistant", "content": "Acme Corp is an enterprise customer."},
        {"role": "user", "content": "What about Q4?"},
    ]
    with patch("app.services.query_rewriter.get_model_router", return_value=router):
        result = await rewrite_for_retrieval("What about Q4?", history, org_id="org-1")
    assert "Acme" in result["refined_query"]
    router.complete.assert_awaited_once()


def test_conflict_detection_flags_opposing_chunks():
    chunks = [
        {"id": "a", "source": "Policy A", "content": "Refunds are enabled for all customers."},
        {"id": "b", "source": "Policy B", "content": "Refunds are disabled for all customers."},
    ]
    conflicts = detect_chunk_conflicts(chunks)
    assert len(conflicts) == 1
    assert conflicts[0]["chunk_a_id"] == "a"


def test_conflict_flagged_chunks_surfaced_in_why_this_answer():
    conflicts = [{"source_a": "Policy A", "source_b": "Policy B", "reason": "opposing statements"}]
    explanation = generate_answer_explanation(
        [{"source": "Policy A", "score": 0.8, "content": "enabled"}],
        conflicts=conflicts,
    )
    assert "conflict" in explanation.lower()


@pytest.mark.asyncio
async def test_validator_catches_unsupported_claims():
    router = MagicMock()
    router.complete = AsyncMock(
        return_value=SimpleNamespace(
            content='{"is_valid": false, "issues": ["unsupported revenue figure"], "confidence": 0.2, "requires_human": true}'
        )
    )
    with patch("app.services.answer_validator.get_model_router", return_value=router):
        result = await validate_grounded_answer(
            "Revenue was $9.9B last quarter.",
            [{"content": "Revenue was $1.2M", "source": "Internal doc"}],
            confidence_threshold=0.4,
        )
    assert result["is_valid"] is False
    assert result["issues"]


@pytest.mark.asyncio
async def test_validator_triggers_regeneration_once():
    intelligence = AgentIntelligence(settings=SimpleNamespace(disable_ai=False, rag_top_k=5))
    intelligence._regenerate_grounded_answer = AsyncMock(return_value="Grounded answer from context.")
    with patch(
        "app.operators.agent_intelligence.validate_grounded_answer",
        AsyncMock(
            side_effect=[
                {"is_valid": False, "issues": ["unsupported"], "confidence": 0.2, "requires_human": True},
                {"is_valid": True, "issues": [], "confidence": 0.8, "requires_human": False},
            ]
        ),
    ):
        result = await intelligence._finalize_assistant_response(
            settings=SimpleNamespace(),
            org_id="org-1",
            mode_key="standard",
            query="What is revenue?",
            answer="Unsupported claim",
            rag_sources=[{"content": "Revenue is $1M", "source": "Doc"}],
            react_result=None,
            engine_settings=SimpleNamespace(
                validation_enabled=True,
                confidence_threshold=0.4,
                performance_mode="balanced",
            ),
            message_id="msg-1",
            client=MagicMock(),
            conflicts=[],
            refined_query=None,
        )
    intelligence._regenerate_grounded_answer.assert_awaited_once()
    assert result["content"] == "Grounded answer from context."


@pytest.mark.asyncio
async def test_validator_returns_safe_fallback_on_second_failure():
    intelligence = AgentIntelligence(settings=SimpleNamespace(disable_ai=False, rag_top_k=5))
    intelligence._regenerate_grounded_answer = AsyncMock(return_value="Still unsupported.")
    with patch(
        "app.operators.agent_intelligence.validate_grounded_answer",
        AsyncMock(
            return_value={"is_valid": False, "issues": ["unsupported"], "confidence": 0.1, "requires_human": True}
        ),
    ):
        result = await intelligence._finalize_assistant_response(
            settings=SimpleNamespace(),
            org_id="org-1",
            mode_key="standard",
            query="What is revenue?",
            answer="Unsupported claim",
            rag_sources=[{"content": "Revenue is $1M", "source": "Doc"}],
            react_result=None,
            engine_settings=SimpleNamespace(
                validation_enabled=True,
                confidence_threshold=0.4,
                performance_mode="balanced",
            ),
            message_id="msg-1",
            client=MagicMock(),
            conflicts=[],
            refined_query=None,
        )
    assert result["content"] == SAFE_FALLBACK


@pytest.mark.asyncio
async def test_validator_skipped_in_fast_mode():
    intelligence = AgentIntelligence(settings=SimpleNamespace(disable_ai=False, rag_top_k=5))
    with patch("app.operators.agent_intelligence.validate_grounded_answer", AsyncMock()) as validator:
        result = await intelligence._finalize_assistant_response(
            settings=SimpleNamespace(),
            org_id="org-1",
            mode_key="fast",
            query="Quick question",
            answer="Fast answer",
            rag_sources=[],
            react_result=None,
            engine_settings=SimpleNamespace(
                validation_enabled=True,
                confidence_threshold=0.4,
                performance_mode="balanced",
            ),
            message_id="msg-1",
            client=MagicMock(),
            conflicts=[],
            refined_query=None,
        )
    validator.assert_not_awaited()
    assert result["content"] == "Fast answer"


@pytest.mark.asyncio
async def test_latency_stages_logged_per_request():
    settings = SimpleNamespace()
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])
    with patch("app.services.latency_tracking.get_supabase_client", return_value=client):
        from app.services.latency_tracking import log_pipeline_latency

        await log_pipeline_latency(
            settings,
            org_id="org-1",
            stage_name="retrieval",
            duration_ms=42,
            message_id="msg-1",
            client=client,
        )
    client.table.assert_called_with("ai_pipeline_latency")


def test_synchronous_confidence_triggers_clarification_below_threshold():
    result = compute_sync_confidence(
        query="status?",
        answer="Maybe.",
        chunks=[{"score": 0.1, "content": "partial"}],
        validation_confidence=0.2,
        conflict_count=1,
    )
    assert result["needs_clarification"] is True
    assert result["score"] < 0.4


def test_why_this_answer_summary_is_audit_readable_not_raw_cot():
    explanation = generate_answer_explanation(
        [
            {"source": "HubSpot deal", "score": 0.91, "content": "Acme renewal"},
            {"source": "Internal playbook", "score": 0.72, "content": "Renewal steps"},
        ],
        reasoning_trace=[{"toolName": "searchKnowledgeBase"}],
    )
    assert "HubSpot" in explanation
    assert "chain" not in explanation.lower()
    assert "thought" not in explanation.lower()


def test_no_duplicate_rag_pipeline_introduced():
    import app.services.unified_retrieval_service as unified
    import app.services.rag_service as rag_service

    source = unified.__file__
    assert source
    with open(rag_service.__file__, encoding="utf-8") as handle:
        rag_source = handle.read()
    assert "class UnifiedRetrievalService" not in rag_source
    assert "retrieve_hybrid_rows" in rag_source
    assert "rrf_merge" in rag_source or "hybrid_rerank" in rag_source
    import glob
    import os

    backend_root = os.path.dirname(os.path.dirname(rag_service.__file__))
    ai_engine_paths = glob.glob(os.path.join(backend_root, "ai_engine", "**", "*.py"), recursive=True)
    assert ai_engine_paths == []


def test_dedupe_chunks_removes_near_duplicates():
    chunks = [
        {"id": "1", "content": "Refund policy allows returns within 30 days.", "score": 0.9},
        {"id": "2", "content": "Refund policy allows returns within 30 days", "score": 0.7},
    ]
    deduped = dedupe_chunks(chunks)
    assert len(deduped) == 1


def test_mode_config_latency_tiers_exist():
    assert set(MODE_CONFIG.keys()) == {"fast", "standard", "reasoning", "agent"}
