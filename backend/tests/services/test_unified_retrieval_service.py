from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.unified_retrieval_service import RetrievalScopes, UnifiedRetrievalService


@pytest.mark.asyncio
async def test_unified_retrieval_composes_bundle():
    rag = MagicMock()
    rag.retrieve_chunks = AsyncMock(
        return_value=(
            [SimpleNamespace(id="c1", content="Policy", score=0.9, source="KB")],
            {"reranked": 1},
        )
    )
    service = UnifiedRetrievalService(settings=SimpleNamespace(rag_top_k=5), rag_service=rag)
    client = MagicMock()

    with patch(
        "app.services.unified_retrieval_service.get_org_context_service"
    ) as mock_org_svc:
        mock_org_svc.return_value.get_snapshot.return_value = {
            "connectedIntegrations": ["hubspot"],
            "orgName": "Acme",
        }
        with patch(
            "app.services.unified_retrieval_service.build_task_retrieval_context",
            return_value={"facts": [{"content": "Prefer email"}]},
        ):
            with patch(
                "app.services.unified_retrieval_service.format_retrieval_prompt_section",
                return_value="<agent_memory>mem</agent_memory>",
            ):
                bundle = await service.retrieve(
                    org_id="org-1",
                    query="What is our refund policy?",
                    client=client,
                    agent={"id": "agent-1", "name": "Support"},
                    environment_name="production",
                )

    rag.retrieve_chunks.assert_awaited_once()
    assert len(bundle.rag_sources) == 1
    assert bundle.org_context["orgName"] == "Acme"
    assert "<knowledge_base>" in bundle.rag_section
    assert bundle.memory_section == "<agent_memory>mem</agent_memory>"
    assert any(source.get("kind") == "knowledge" for source in bundle.sources)


@pytest.mark.asyncio
async def test_unified_retrieval_respects_scopes():
    rag = MagicMock()
    rag.retrieve_chunks = AsyncMock(return_value=([], {}))
    service = UnifiedRetrievalService(settings=SimpleNamespace(rag_top_k=5), rag_service=rag)

    with patch("app.services.unified_retrieval_service.get_org_context_service") as mock_org_svc:
        bundle = await service.retrieve(
            org_id="org-1",
            query="test",
            client=MagicMock(),
            agent={"id": "agent-1"},
            scopes=RetrievalScopes(knowledge=False, org_context=False, agent_memory=False),
        )

    mock_org_svc.return_value.get_snapshot.assert_not_called()
    rag.retrieve_chunks.assert_not_awaited()
    assert bundle.rag_sources == []
    assert bundle.org_context == {}


@pytest.mark.asyncio
async def test_retrieve_knowledge_rows_maps_be10_shape():
    rag = MagicMock()
    rag.retrieve_hybrid_rows = AsyncMock(
        return_value=(
            [
                {
                    "chunk_id": "c1",
                    "content": "Policy text",
                    "source_id": "src-1",
                    "source_title": "HR",
                    "document_id": "doc-1",
                    "document_title": "Handbook",
                    "chunk_index": 2,
                    "score": 0.91,
                }
            ],
            {"reranked": 1},
        )
    )
    service = UnifiedRetrievalService(settings=SimpleNamespace(rag_top_k=5), rag_service=rag)

    rows, metrics = await service.retrieve_knowledge_rows(
        org_id="org-1",
        query="refund policy",
        top_k=5,
        environment_name="production",
        agent_id="agent-1",
        min_score=0.5,
    )

    rag.retrieve_hybrid_rows.assert_awaited_once()
    assert metrics["reranked"] == 1
    assert rows[0]["chunk_id"] == "c1"
    assert rows[0]["content"] == "Policy text"
    assert rows[0]["source_id"] == "src-1"
    assert rows[0]["chunk_index"] == 2


def test_hybrid_row_to_be10_row_defaults_missing_metadata():
    from app.services.unified_retrieval_service import hybrid_row_to_be10_row

    row = hybrid_row_to_be10_row({"id": "abc", "content": "hello", "score": 0.5, "title": "Doc"})
    assert row["chunk_id"] == "abc"
    assert row["source_title"] == "Doc"
    assert row["source_id"] == ""
    assert row["chunk_index"] == 0
