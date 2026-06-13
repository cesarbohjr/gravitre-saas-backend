"""Hybrid RAG retrieval helpers — BM25, RRF, cross-encoder rerank (STA-150)."""
from __future__ import annotations

import re
from typing import Any

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

RRF_K = 60.0
_TOKEN_PATTERN = re.compile(r"\w+")


def hybrid_candidate_k(settings: Settings) -> int:
    value = int(getattr(settings, "rag_hybrid_candidate_k", 0) or 20)
    return max(5, min(value, 50))


def rerank_score_threshold(settings: Settings) -> float:
    value = float(getattr(settings, "rag_rerank_score_threshold", 0.3) or 0.3)
    return min(max(value, 0.0), 1.0)


def cross_encoder_enabled(settings: Settings) -> bool:
    if getattr(settings, "rag_disable_cross_encoder", False):
        return False
    return bool(getattr(settings, "rag_cross_encoder_enabled", True))


def normalize_chunk_row(row: dict[str, Any]) -> dict[str, Any]:
    title = (
        row.get("title")
        or row.get("document_title")
        or row.get("source_title")
        or ""
    )
    return {
        "id": str(row.get("id") or row.get("chunk_id") or ""),
        "content": str(row.get("content") or ""),
        "score": float(row.get("score") or 0.0),
        "title": str(title),
    }


def tokenize_for_bm25(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def bm25_rank_rows(query: str, rows: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    if not rows or not query.strip():
        return []
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning("rank_bm25 unavailable; falling back to lexical overlap for keyword retrieval")
        return _lexical_rank_rows(query, rows, top_k)

    corpus_tokens = [tokenize_for_bm25(str(row.get("content") or "")) for row in rows]
    if not any(corpus_tokens):
        return []
    bm25 = BM25Okapi(corpus_tokens)
    query_tokens = tokenize_for_bm25(query)
    if not query_tokens:
        return []
    scores = bm25.get_scores(query_tokens)
    ranked: list[dict[str, Any]] = []
    for row, score in zip(rows, scores):
        item = dict(row)
        item["score"] = float(score)
        ranked.append(item)
    ranked.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return ranked[:top_k]


def rrf_merge(
    semantic_rows: list[dict[str, Any]],
    keyword_rows: list[dict[str, Any]],
    *,
    top_k: int,
    rrf_k: float = RRF_K,
) -> list[dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for rank, row in enumerate(semantic_rows, start=1):
        normalized = normalize_chunk_row(row)
        row_id = normalized["id"]
        if not row_id:
            continue
        if row_id not in scores:
            scores[row_id] = normalized
            scores[row_id]["score"] = 0.0
        scores[row_id]["score"] += 1.0 / (rrf_k + rank)
    for rank, row in enumerate(keyword_rows, start=1):
        normalized = normalize_chunk_row(row)
        row_id = normalized["id"]
        if not row_id:
            continue
        if row_id not in scores:
            scores[row_id] = normalized
            scores[row_id]["score"] = 0.0
        scores[row_id]["score"] += 1.0 / (rrf_k + rank)
    merged = list(scores.values())
    merged.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return merged[:top_k]


def rerank_rows(
    query: str,
    rows: list[dict[str, Any]],
    *,
    top_k: int,
    settings: Settings,
) -> tuple[list[dict[str, Any]], str]:
    if not rows:
        return [], "none"
    if cross_encoder_enabled(settings):
        reranked, method = _cross_encoder_rerank(query, rows, top_k=top_k, settings=settings)
        if reranked:
            return reranked, method
    return _lexical_rerank(query, rows, top_k=top_k), "lexical_overlap"


def _lexical_rank_rows(query: str, rows: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    q_terms = set(tokenize_for_bm25(query))
    ranked: list[dict[str, Any]] = []
    for row in rows:
        content_terms = set(tokenize_for_bm25(str(row.get("content") or "")))
        overlap = len(q_terms & content_terms)
        item = dict(row)
        item["score"] = float(overlap)
        ranked.append(item)
    ranked.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return ranked[:top_k]


def _lexical_rerank(query: str, rows: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    q_terms = set(tokenize_for_bm25(query))
    ranked: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        content = str(item.get("content") or "").lower()
        overlap = len([term for term in q_terms if term in content])
        item["score"] = float(item.get("score") or 0.0) + overlap * 0.05
        ranked.append(item)
    ranked.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return ranked[:top_k]


_cross_encoder_model: Any | None = None
_cross_encoder_model_name: str | None = None


def _get_cross_encoder(settings: Settings) -> Any:
    global _cross_encoder_model, _cross_encoder_model_name
    model_name = (
        getattr(settings, "rag_cross_encoder_model", None)
        or "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ).strip()
    if _cross_encoder_model is not None and _cross_encoder_model_name == model_name:
        return _cross_encoder_model
    from sentence_transformers import CrossEncoder

    logger.info("rag_cross_encoder_loading model=%s", model_name)
    _cross_encoder_model = CrossEncoder(model_name)
    _cross_encoder_model_name = model_name
    return _cross_encoder_model


def _cross_encoder_rerank(
    query: str,
    rows: list[dict[str, Any]],
    *,
    top_k: int,
    settings: Settings,
) -> tuple[list[dict[str, Any]], str]:
    try:
        encoder = _get_cross_encoder(settings)
    except ImportError:
        logger.warning("sentence_transformers unavailable; skipping cross-encoder rerank")
        return [], "cross_encoder_unavailable"
    except Exception as exc:  # noqa: BLE001
        logger.warning("cross_encoder_load_failed error=%s", str(exc))
        return [], "cross_encoder_load_failed"

    pairs = [[query, str(row.get("content") or "")] for row in rows]
    try:
        scores = encoder.predict(pairs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cross_encoder_predict_failed error=%s", str(exc))
        return [], "cross_encoder_predict_failed"

    scored: list[dict[str, Any]] = []
    for row, score in zip(rows, scores):
        item = dict(row)
        item["score"] = float(score)
        scored.append(item)
    scored.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)

    threshold = rerank_score_threshold(settings)
    filtered = [row for row in scored if float(row.get("score") or 0.0) >= threshold]
    if not filtered:
        filtered = scored[:top_k]
    return filtered[:top_k], "cross_encoder"


def reset_cross_encoder_cache() -> None:
    """Test helper to drop lazy-loaded encoder."""
    global _cross_encoder_model, _cross_encoder_model_name
    _cross_encoder_model = None
    _cross_encoder_model_name = None
