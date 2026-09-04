"""GraphRAG relationship traversal — Acme / Q3 pipeline scenario."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.task_classifier import TaskClassifier


@pytest.mark.asyncio
async def test_acme_relationship_query_uses_multi_hop():
    service = KnowledgeGraphService()
    question = "How is Acme related to our Q3 pipeline decline?"

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": "acme-node", "node_type": "company", "name": "Acme Corp"},
    ]

    hop_chain = [
        {
            "entityType": "deal",
            "entityId": "deal-q3",
            "relationshipType": "contributes_to",
            "confidence": 0.88,
        },
        {
            "entityType": "kpi",
            "entityId": "pipeline-q3",
            "relationshipType": "impacts",
            "confidence": 0.82,
        },
    ]

    call_count = {"n": 0}

    async def _neighbors(org_id, entity_type, entity_id, **kwargs):
        _ = org_id, kwargs
        call_count["n"] += 1
        if entity_type == "company" and entity_id == "acme-node":
            return [hop_chain[0]]
        if entity_type == "deal" and entity_id == "deal-q3":
            return [hop_chain[1]]
        return []

    with patch(
        "app.services.knowledge_graph_service.get_related_entities",
        side_effect=_neighbors,
    ):
        result = await service.answer_business_question(
            "org-1",
            question,
            client=mock_client,
        )

    assert result["status"] == "ok"
    assert result["queryShape"] == "relationship"
    assert result["identifiedEntity"]["entityId"] == "acme-node"
    assert result["traversal"]["paths"]
    assert call_count["n"] >= 1
    assert any(
        "pipeline" in str(p.get("entityId", "")).lower()
        or "pipeline" in str(p.get("pathSummary", "")).lower()
        for p in result["traversal"]["paths"]
    )


@pytest.mark.asyncio
async def test_task_classifier_flags_relationship_lookup():
    classifier = TaskClassifier()
    with patch.object(
        classifier,
        "_classify_with_ml",
        new=AsyncMock(return_value={"intent": "question_answering", "classification_confidence": 0.8}),
    ):
        result = await classifier.classify(
            "org-1",
            "How is Acme related to our Q3 pipeline decline?",
        )
    assert result["intent"] == "relationship_lookup"
    assert result["requires_graph"] is True
