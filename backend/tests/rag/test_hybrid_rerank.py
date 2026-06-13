"""Tests for hybrid RAG reranking (STA-150)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.rag import hybrid_rerank as hybrid


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
        rag_rerank_score_threshold=0.3,
        rag_cross_encoder_enabled=True,
        rag_disable_cross_encoder=False,
    )
    base.update(overrides)
    return Settings(**base)


def test_rrf_merge_deduplicates_and_boosts_overlap():
    semantic = [{"id": "a", "content": "alpha", "score": 0.9}]
    keyword = [{"id": "a", "content": "alpha", "score": 1.2}, {"id": "b", "content": "beta", "score": 0.8}]
    merged = hybrid.rrf_merge(semantic, keyword, top_k=3)
    assert len(merged) == 2
    assert merged[0]["id"] == "a"


def test_bm25_rank_rows_prefers_matching_terms():
    rows = [
        {"id": "1", "content": "pipeline hygiene for revenue operations"},
        {"id": "2", "content": "unrelated finance memo"},
    ]
    ranked = hybrid.bm25_rank_rows("pipeline revenue", rows, top_k=2)
    assert ranked[0]["id"] == "1"


def test_normalize_chunk_row_maps_rpc_fields():
    row = hybrid.normalize_chunk_row(
        {"chunk_id": "chunk-1", "content": "hello", "document_title": "Doc", "score": 0.5}
    )
    assert row["id"] == "chunk-1"
    assert row["title"] == "Doc"


def test_rerank_rows_uses_cross_encoder_when_enabled():
    hybrid.reset_cross_encoder_cache()
    rows = [
        {"id": "a", "content": "inactive leads in CRM", "score": 0.2},
        {"id": "b", "content": "weather report", "score": 0.2},
    ]
    encoder = MagicMock()
    encoder.predict.return_value = [0.9, 0.1]

    with patch.object(hybrid, "_get_cross_encoder", return_value=encoder):
        reranked, method = hybrid.rerank_rows(
            "inactive leads campaign",
            rows,
            top_k=1,
            settings=_settings(),
        )

    assert method == "cross_encoder"
    assert len(reranked) == 1
    assert reranked[0]["id"] == "a"
    assert reranked[0]["score"] == 0.9


def test_rerank_rows_filters_below_threshold():
    hybrid.reset_cross_encoder_cache()
    rows = [
        {"id": "a", "content": "low relevance", "score": 0.2},
        {"id": "b", "content": "also low", "score": 0.2},
    ]
    encoder = MagicMock()
    encoder.predict.return_value = [0.1, 0.2]

    with patch.object(hybrid, "_get_cross_encoder", return_value=encoder):
        reranked, method = hybrid.rerank_rows(
            "query",
            rows,
            top_k=2,
            settings=_settings(rag_rerank_score_threshold=0.3),
        )

    assert method == "cross_encoder"
    assert len(reranked) == 2
    assert reranked[0]["id"] == "b"


def test_rerank_rows_falls_back_when_cross_encoder_disabled():
    rows = [{"id": "a", "content": "inactive leads campaign", "score": 0.2}]
    reranked, method = hybrid.rerank_rows(
        "inactive leads",
        rows,
        top_k=1,
        settings=_settings(rag_disable_cross_encoder=True),
    )
    assert method == "lexical_overlap"
    assert reranked[0]["id"] == "a"
