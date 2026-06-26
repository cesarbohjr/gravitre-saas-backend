from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.response_evaluation_service import (
    COMPOSITE_SCORE_WEIGHTS,
    compute_composite_score,
    consolidate_evaluation,
)


def test_composite_score_renormalizes_missing_signals():
    full = compute_composite_score(
        {
            "rag_quality_score": 0.8,
            "user_feedback": "helpful",
            "chunk_reliability_avg": 0.6,
        }
    )
    without_feedback = compute_composite_score(
        {
            "rag_quality_score": 0.8,
            "chunk_reliability_avg": 0.6,
        }
    )
    assert full == pytest.approx(0.84, abs=0.01)
    expected = (
        COMPOSITE_SCORE_WEIGHTS["rag_quality_score"] * 0.8
        + COMPOSITE_SCORE_WEIGHTS["chunk_reliability_avg"] * 0.6
    ) / (
        COMPOSITE_SCORE_WEIGHTS["rag_quality_score"] + COMPOSITE_SCORE_WEIGHTS["chunk_reliability_avg"]
    )
    assert without_feedback == pytest.approx(round(expected, 4))


@pytest.mark.asyncio
async def test_returns_none_when_feedback_not_yet_arrived():
    client = MagicMock()

    def table(name):
        t = MagicMock()
        if name == "message_feedback":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )
        elif name == "user_query_patterns":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"feedback_helpful": None, "rag_quality_score": 0.7, "response_time_ms": 120, "surface": "assistant"}]
            )
        return t

    client.table.side_effect = table
    with patch("app.services.response_evaluation_service.get_supabase_client", return_value=client):
        result = await consolidate_evaluation(MagicMock(), "org-1", "msg-1", client=client)
    assert result is None


@pytest.mark.asyncio
async def test_consolidates_signals_into_one_record():
    client = MagicMock()
    upsert_payload: dict = {}

    def table(name):
        t = MagicMock()
        if name == "message_feedback":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"feedback": "helpful", "reason": "accurate"}]
            )
        elif name == "user_query_patterns":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "feedback_helpful": True,
                        "rag_quality_score": 0.85,
                        "response_time_ms": 250,
                        "surface": "assistant",
                    }
                ]
            )
        elif name == "rag_chunk_outcomes":
            t.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "source_document_id": "doc-1",
                        "rerank_score": 0.9,
                        "outcome_helpful": True,
                        "retrieval_latency_ms": 40,
                    },
                    {
                        "source_document_id": "doc-2",
                        "rerank_score": 0.7,
                        "outcome_helpful": False,
                        "retrieval_latency_ms": 40,
                    },
                ]
            )
        elif name == "response_evaluations":

            def upsert(row, on_conflict=None):
                upsert_payload.update(row)
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[row])
                return chain

            t.upsert.side_effect = upsert
        return t

    client.table.side_effect = table
    with patch("app.services.response_evaluation_service.get_supabase_client", return_value=client):
        result = await consolidate_evaluation(MagicMock(), "org-1", "msg-1", client=client)

    assert result is not None
    assert result["user_feedback"] == "helpful"
    assert result["rag_quality_score"] == 0.85
    assert result["response_latency_ms"] == 250
    assert result["chunk_outcome_summary"]["chunks_used"] == 2
    assert result["composite_score"] > 0
    assert upsert_payload["message_id"] == "msg-1"
