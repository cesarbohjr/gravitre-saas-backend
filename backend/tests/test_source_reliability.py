from __future__ import annotations

import pytest

from app.ml.source_reliability import (
    RAG_RERANKING_ACTIVATION_MIN_SCORED_SOURCES,
    apply_reliability_adjustment,
    compute_source_reliability,
)


def test_compute_source_reliability_requires_min_outcomes():
    assert compute_source_reliability(8, 9) is None
    assert compute_source_reliability(7, 10) == pytest.approx(0.7)


def test_apply_reliability_adjustment_skips_until_activation_gate():
    rows = [{"id": "a", "document_id": "doc-1", "score": 0.9}]
    scores = {"doc-1": 0.8, "doc-2": 0.6}
    unchanged = apply_reliability_adjustment(rows, scores, 0.15)
    assert unchanged == rows
    enough_scores = {f"doc-{idx}": 0.5 + idx * 0.05 for idx in range(RAG_RERANKING_ACTIVATION_MIN_SCORED_SOURCES)}
    adjusted = apply_reliability_adjustment(rows, enough_scores, 0.15)
    assert adjusted[0]["final_score"] == pytest.approx(0.9 + 0.15 * enough_scores["doc-1"])
