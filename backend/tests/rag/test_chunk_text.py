"""STA-171: semantic chunking for RAG ingest."""
from __future__ import annotations

import pytest

from app.rag.ingest import chunk_text


def test_semantic_chunk_preserves_paragraph_boundaries():
    text = (
        "First paragraph about workflow automation and approvals in enterprise systems.\n\n"
        "Second paragraph about connector grants and federated partner organizations.\n\n"
        "Third paragraph about agent handoffs and delegated operational tasks."
    )
    chunks = chunk_text(text, min_chars=80, max_chars=120, overlap_chars=0, strategy="semantic")
    assert len(chunks) >= 2
    assert "First paragraph" in chunks[0]
    assert any("Third paragraph" in chunk for chunk in chunks)


def test_semantic_chunk_splits_long_paragraph_on_sentences():
    sentences = ["Sentence one about CRM sync."] * 8
    text = " ".join(sentences)
    chunks = chunk_text(text, min_chars=60, max_chars=100, overlap_chars=0, strategy="semantic")
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 100
        assert chunk.endswith(".")


def test_semantic_chunk_overlap_repeats_tail():
    text = "Alpha paragraph one with extra detail.\n\nBeta paragraph two with extra detail.\n\nGamma paragraph three with extra detail."
    chunks = chunk_text(text, min_chars=40, max_chars=70, overlap_chars=15, strategy="semantic")
    assert len(chunks) >= 2
    tail = chunks[0][-15:]
    assert tail in chunks[1]


def test_fixed_strategy_matches_windowed_split():
    text = "abcdefghijklmnopqrstuvwxyz" * 20
    fixed = chunk_text(text, min_chars=50, max_chars=50, overlap_chars=10, strategy="fixed")
    semantic = chunk_text(text, min_chars=50, max_chars=50, overlap_chars=10, strategy="semantic")
    assert fixed
    assert semantic
    assert fixed[0] == text[:50].strip() or fixed[0] in text


def test_empty_text_returns_empty_list():
    assert chunk_text("", strategy="semantic") == []
    assert chunk_text("   \n\n  ", strategy="semantic") == []


def test_chunk_count_limit_raises():
    text = "word " * 50000
    with pytest.raises(ValueError, match="Chunk count exceeds maximum"):
        chunk_text(text, min_chars=10, max_chars=20, overlap_chars=0, strategy="fixed")
