from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rag_service import Document, RAGService


@pytest.fixture
def service(mock_settings) -> RAGService:
    with patch("app.services.rag_service.get_settings", return_value=mock_settings):
        return RAGService()


def test_rrf_merge_and_rerank(service: RAGService):
    semantic = [{"id": "a", "content": "lead scoring workflow", "score": 0.9}, {"id": "b", "content": "email campaign", "score": 0.8}]
    keyword = [{"id": "b", "content": "email campaign", "score": 0.4}, {"id": "c", "content": "inactive leads", "score": 0.4}]
    merged = service._rrf_merge(semantic, keyword, top_k=3)  # noqa: SLF001
    assert len(merged) == 3
    reranked = service._rerank("inactive leads campaign", merged, top_k=2)  # noqa: SLF001
    assert len(reranked) == 2
    assert reranked[0]["id"] in {"b", "c"}


@pytest.mark.asyncio
async def test_ingest_document(service: RAGService):
    mock_client = MagicMock()
    with patch("app.services.rag_service.get_supabase_client", return_value=mock_client):
        with patch("app.services.rag_service.upsert_document", return_value={"id": "doc-1"}):
            with patch("app.services.rag_service.chunk_text", return_value=["chunk 1", "chunk 2"]):
                with patch("app.services.rag_service.replace_chunks_and_embeddings", return_value=2):
                    chunks = await service.ingest_document(
                        org_id="org-1",
                        document=Document(source_id="src-1", title="Title", content="Body text"),
                    )
    assert len(chunks) == 2
    assert chunks[0].id == "doc-1:0"


@pytest.mark.asyncio
async def test_query_pipeline(service: RAGService):
    semantic_rows = [
        {"id": "a", "content": "Sky is blue by Rayleigh scattering", "score": 0.9, "title": "Science"},
        {"id": "b", "content": "Clouds scatter light", "score": 0.7, "title": "Science"},
    ]
    keyword_rows = [{"id": "b", "content": "Clouds scatter light", "score": 0.4, "title": "Science"}]
    with patch("app.services.rag_service.get_embedding", return_value=[0.1] * 1536):
        with patch("app.services.rag_service.search_chunks", return_value=semantic_rows):
            with patch.object(service, "_keyword_search", return_value=keyword_rows):
                with patch.object(
                    service.model_router,
                    "complete",
                    AsyncMock(return_value=SimpleNamespace(content="Because molecules scatter shorter wavelengths first.")),
                ):
                    response = await service.query(org_id="org-1", query="Why is the sky blue?", top_k=2)
    assert response.answer
    assert len(response.chunks) == 2
    assert response.metrics["top_k"] == 2
