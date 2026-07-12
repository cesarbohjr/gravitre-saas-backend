"""STA-313 Knowledge Phase 2 rerank eval metrics (hermetic)."""
from __future__ import annotations

from pathlib import Path

from app.rag.rerank_eval import (
    compare_results,
    evaluate_reranker,
    load_eval_bundle,
    make_lexical_reranker,
    mrr,
    precision_at_k,
)

REPO = Path(__file__).resolve().parents[3]
QUERIES = REPO / "docs" / "delivery" / "sta313-rerank-eval-queries.json"


def test_precision_and_mrr_helpers():
    relevant = frozenset({"a", "b"})
    assert precision_at_k(["a", "x", "b"], relevant, k=3) == 1.0
    assert precision_at_k(["x", "y", "a"], relevant, k=3) == 0.5
    assert mrr(["x", "a", "b"], relevant) == 0.5


def test_lexical_baseline_scores_fixed_query_set():
    queries, corpus = load_eval_bundle(QUERIES)
    assert len(queries) >= 5
    assert len(corpus) >= 8
    result = evaluate_reranker(
        "lexical_overlap",
        make_lexical_reranker(),
        queries,
        corpus,
        top_k=3,
    )
    assert result["status"] == "ok"
    assert result["n_queries_scored"] == len(queries)
    assert 0.0 <= result["mean_precision_at_k"] <= 1.0
    assert 0.0 <= result["mean_mrr"] <= 1.0


def test_compare_results_requires_measured_win():
    baseline = {
        "name": "ms-marco",
        "status": "ok",
        "top_k": 3,
        "mean_precision_at_k": 0.7,
        "mean_mrr": 0.8,
    }
    weak = {
        "name": "candidate-weak",
        "status": "ok",
        "mean_precision_at_k": 0.7,
        "mean_mrr": 0.8,
    }
    strong = {
        "name": "candidate-strong",
        "status": "ok",
        "mean_precision_at_k": 0.85,
        "mean_mrr": 0.9,
    }
    no_win = compare_results(baseline, [weak])
    assert no_win["upgrade_authorized"] is False
    win = compare_results(baseline, [strong])
    assert win["upgrade_authorized"] is True
    assert "candidate-strong" in win["winners"]
