from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_org_context, require_admin
from app.main import app


@pytest.fixture
async def admin_client():
    org_id = "org-a-1111"

    async def _org_context():
        return org_id

    app.dependency_overrides[get_org_context] = _org_context
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin-1"}, org_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, org_id
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_evaluations_endpoint_returns_v7_payload(admin_client):
    client, org_id = admin_client
    payload = {
        "summary": {
            "totalEvaluations": 2,
            "pageCount": 2,
            "helpfulCount": 1,
            "notHelpfulCount": 1,
            "avgCompositeScore": 0.72,
            "avgRagQualityScore": 0.8,
            "avgRetrievalLatencyMs": 40.0,
            "avgResponseLatencyMs": 250.0,
        },
        "compositeScoreWeights": {
            "ragQualityScore": 0.4,
            "userFeedback": 0.4,
            "chunkReliabilityAvg": 0.2,
        },
        "retrievalRanker": {
            "trainingExamples": 12,
            "minTrainingExamples": 100,
            "isTrained": False,
            "isDeployed": False,
            "activeReliabilityWeight": 0.15,
            "fallbackReliabilityWeight": 0.15,
            "usingLearnedWeight": False,
            "modelName": "company-retrieval-ranker",
        },
        "evaluations": [
            {
                "id": "eval-1",
                "messageId": "msg-1",
                "surface": "assistant",
                "ragQualityScore": 0.85,
                "userFeedback": "helpful",
                "feedbackReason": None,
                "chunkOutcomeSummary": {
                    "chunksUsed": 3,
                    "avgReliability": 0.7,
                    "flaggedStaleSources": [],
                    "retrievalLatencyMs": 40,
                },
                "retrievalLatencyMs": 40,
                "responseLatencyMs": 250,
                "compositeScore": 0.84,
                "evaluatedAt": "2026-06-26T12:00:00+00:00",
            }
        ],
        "pagination": {"limit": 50, "offset": 0, "hasMore": False},
    }
    with patch(
        "app.routers.admin_intelligence.load_admin_response_evaluations",
        new=AsyncMock(return_value=payload),
    ) as mock_load:
        resp = await client.get("/api/admin/intelligence/evaluations?limit=25&sinceDays=30")
        assert resp.status_code == 200
        body = resp.json()
        mock_load.assert_awaited_once()
        assert mock_load.await_args.args[1] == org_id
        assert mock_load.await_args.kwargs["limit"] == 25
        assert mock_load.await_args.kwargs["since_days"] == 30
        assert body["evaluations"][0]["messageId"] == "msg-1"
        assert body["retrievalRanker"]["fallbackReliabilityWeight"] == 0.15


@pytest.mark.asyncio
async def test_load_admin_response_evaluations_serializes_rows():
    from app.services.response_evaluation_service import load_admin_response_evaluations

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "eval-1",
                "message_id": "msg-1",
                "surface": "assistant",
                "rag_quality_score": 0.9,
                "user_feedback": "helpful",
                "feedback_reason": "accurate",
                "chunk_outcome_summary": {
                    "chunks_used": 2,
                    "avg_reliability": 0.6,
                    "flagged_stale_sources": [],
                    "retrieval_latency_ms": 35,
                },
                "retrieval_latency_ms": 35,
                "response_latency_ms": 180,
                "composite_score": 0.88,
                "evaluated_at": "2026-06-26T12:00:00+00:00",
            }
        ],
        count=1,
    )

    with patch(
        "app.services.response_evaluation_service._load_retrieval_ranker_status",
        new=AsyncMock(
            return_value={
                "trainingExamples": 0,
                "minTrainingExamples": 100,
                "isTrained": False,
                "isDeployed": False,
                "activeReliabilityWeight": 0.15,
                "fallbackReliabilityWeight": 0.15,
                "usingLearnedWeight": False,
                "modelName": "company-retrieval-ranker",
            }
        ),
    ):
        result = await load_admin_response_evaluations(
            MagicMock(),
            "org-1",
            client=client,
        )

    assert result["summary"]["totalEvaluations"] == 1
    assert result["evaluations"][0]["messageId"] == "msg-1"
    assert result["evaluations"][0]["chunkOutcomeSummary"]["chunksUsed"] == 2
    assert result["compositeScoreWeights"]["userFeedback"] == 0.4
