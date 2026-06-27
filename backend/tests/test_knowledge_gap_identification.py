from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.knowledge_intelligence_service import identify_knowledge_gaps


@pytest.mark.asyncio
async def test_failed_search_cluster_becomes_gap():
    client = MagicMock()
    delete_chain = MagicMock()
    delete_chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    client.table.return_value.delete.return_value = delete_chain
    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(
        data=[
            {
                "id": "gap-1",
                "description": "12 queries about 'QBR materials' failed",
                "failed_query_count": 12,
                "status": "open",
            }
        ]
    )
    client.table.return_value.insert.return_value = insert_chain

    clusters = [
        {
            "id": "cluster-1",
            "cluster_label": "QBR materials",
            "failed_search_count": 12,
            "representative_queries": ["Where is the QBR deck?", "Find QBR slides"],
        }
    ]
    router = MagicMock()
    router.complete = AsyncMock(return_value=MagicMock(content="Add a QBR runbook with deck links."))

    gaps = await identify_knowledge_gaps(
        MagicMock(),
        "org-1",
        clusters,
        client=client,
        router=router,
        min_failed=3,
    )
    assert len(gaps) == 1
    assert gaps[0]["failed_query_count"] == 12
    assert "QBR" in gaps[0]["description"] or "qbr" in gaps[0]["description"].lower()


@pytest.mark.asyncio
async def test_gap_includes_suggested_content():
    client = MagicMock()
    delete_chain = MagicMock()
    delete_chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    client.table.return_value.delete.return_value = delete_chain
    suggestion = "Consider adding a runbook covering quarterly business review deck locations."
    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(
        data=[{"id": "gap-2", "suggested_content": suggestion, "status": "open", "failed_query_count": 5}]
    )
    client.table.return_value.insert.return_value = insert_chain

    router = MagicMock()
    router.complete = AsyncMock(return_value=MagicMock(content=suggestion))

    gaps = await identify_knowledge_gaps(
        MagicMock(),
        "org-1",
        [
            {
                "id": "c1",
                "cluster_label": "QBR materials",
                "failed_search_count": 5,
                "representative_queries": ["QBR deck?"],
            }
        ],
        client=client,
        router=router,
        min_failed=3,
    )
    assert gaps[0]["suggested_content"] == suggestion
