"""Tests for local tool-retrieval embeddings + query cache."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.rag.tool_retrieval_embedding import (
    embed_tool_retrieval_query_timed,
    normalize_tool_retrieval_query,
    reset_tool_retrieval_encoder_for_tests,
)


def test_normalize_tool_retrieval_query():
    assert normalize_tool_retrieval_query("  Send   Email  ") == "send email"


def test_query_cache_hit_on_repeat():
    settings = MagicMock(
        unified_turn_tool_embed_local=True,
        unified_turn_tool_embed_model="test-model",
        unified_turn_tool_query_cache_ttl_sec=300,
    )
    calls = {"n": 0}

    def fake_encode(texts, settings):
        calls["n"] += 1
        return [[float(len(t)), 0.0, 0.0] for t in texts]

    reset_tool_retrieval_encoder_for_tests()
    with patch("app.rag.tool_retrieval_embedding._use_local_tool_embed", return_value=True), patch(
        "app.rag.tool_retrieval_embedding.embed_tool_retrieval_texts",
        side_effect=fake_encode,
    ):
        vec1, stats1 = embed_tool_retrieval_query_timed("Send an email", settings)
        vec2, stats2 = embed_tool_retrieval_query_timed("send an email", settings)
    assert vec1 == vec2
    assert calls["n"] == 1
    assert stats1["embed_query_cache_hit"] is False
    assert stats2["embed_query_cache_hit"] is True
    assert stats2["embed_query_ms"] <= stats1["embed_query_ms"]
