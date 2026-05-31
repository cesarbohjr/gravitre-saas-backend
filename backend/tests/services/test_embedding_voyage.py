"""Tests for Voyage embedding config gate and dimension mismatch handling."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.rag.embedding import EmbeddingDimensionMismatchError, embed_with_failover


def _settings(**kw) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="a",
        supabase_service_role_key="s",
        supabase_jwt_secret="j",
        openai_api_key="",
        voyage_api_key="vk-test",
        voyage_embedding_enabled=False,
        openai_embedding_dimension=1536,
    )
    base.update(kw)
    return Settings(**base)


def test_voyage_skipped_when_disabled():
    with pytest.raises(ValueError, match="voyage: disabled"):
        embed_with_failover("hello", _settings())


def test_dimension_mismatch_raises_when_enabled():
    with pytest.raises(EmbeddingDimensionMismatchError, match="dimension mismatch"):
        embed_with_failover("hello", _settings(voyage_embedding_enabled=True, openai_api_key=""))


@pytest.mark.asyncio
async def test_rag_dimension_mismatch_metadata(mock_settings):
    from app.services.rag_service import RAGService

    mock_settings.voyage_embedding_enabled = True
    mock_settings.openai_api_key = ""
    with patch("app.services.rag_service.get_settings", return_value=mock_settings):
        service = RAGService()
    with patch(
        "app.services.rag_service.embed_with_failover",
        side_effect=EmbeddingDimensionMismatchError("dimension mismatch"),
    ):
        with patch.object(service, "_keyword_search", return_value=[{"id": "k1", "content": "x", "score": 0.5}]):
            resp = await service.query("org-1", "test query")
    assert resp.metrics["embedding_method"] == "keyword_fallback_dimension_mismatch"
