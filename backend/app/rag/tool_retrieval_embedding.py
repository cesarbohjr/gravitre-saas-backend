"""Local + cached embeddings for unified-turn tool retrieval (query + tool docs).

Tool retrieval uses a small in-process SentenceTransformer instead of remote OpenAI
embeddings to avoid ~400ms+ network RTT on every query. Tool-doc vectors are warmed
at boot; query vectors use a short-TTL normalized-text cache.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_ENCODER_LOCK = threading.Lock()
_ENCODER: Any | None = None
_ENCODER_MODEL: str | None = None

_QUERY_CACHE_LOCK = threading.Lock()
# key -> (expires_monotonic, vector)
_QUERY_CACHE: dict[str, tuple[float, list[float]]] = {}


def _tool_embed_model(settings: Settings) -> str:
    return (
        str(getattr(settings, "unified_turn_tool_embed_model", None) or "").strip()
        or "all-MiniLM-L6-v2"
    )


def tool_retrieval_embed_model(settings: Settings) -> str:
    return _tool_embed_model(settings)


def _use_local_tool_embed(settings: Settings) -> bool:
    if not bool(getattr(settings, "unified_turn_tool_embed_local", True)):
        return False
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def normalize_tool_retrieval_query(text: str) -> str:
    return " ".join((text or "").strip().lower().split()) or "task"


def _query_cache_key(model: str, text: str) -> str:
    return f"{model}:{normalize_tool_retrieval_query(text)}"


def _query_cache_ttl_sec(settings: Settings) -> int:
    return max(30, int(getattr(settings, "unified_turn_tool_query_cache_ttl_sec", 300) or 300))


def _get_sentence_encoder(settings: Settings) -> Any:
    global _ENCODER, _ENCODER_MODEL
    model_name = _tool_embed_model(settings)
    with _ENCODER_LOCK:
        if _ENCODER is not None and _ENCODER_MODEL == model_name:
            return _ENCODER
        from sentence_transformers import SentenceTransformer

        logger.info("unified_turn_tool_embed_loading model=%s", model_name)
        t0 = time.perf_counter()
        _ENCODER = SentenceTransformer(model_name)
        _ENCODER_MODEL = model_name
        logger.info(
            "unified_turn_tool_embed_loaded model=%s ms=%s",
            model_name,
            int((time.perf_counter() - t0) * 1000),
        )
        return _ENCODER


def reset_tool_retrieval_encoder_for_tests() -> None:
    """Clear cached encoder and query cache (tests only)."""
    global _ENCODER, _ENCODER_MODEL
    with _ENCODER_LOCK:
        _ENCODER = None
        _ENCODER_MODEL = None
    with _QUERY_CACHE_LOCK:
        _QUERY_CACHE.clear()


def embed_tool_retrieval_texts(
    texts: list[str],
    settings: Settings,
) -> list[list[float]]:
    """Batch-encode texts with the local tool-retrieval model."""
    cleaned = [str(t or "").strip() or " " for t in texts]
    if not cleaned:
        return []
    encoder = _get_sentence_encoder(settings)
    vectors = encoder.encode(cleaned, normalize_embeddings=True, show_progress_bar=False)
    return [list(map(float, row)) for row in vectors]


def embed_tool_retrieval_query_timed(
    text: str,
    settings: Settings,
) -> tuple[list[float], dict[str, Any]]:
    """Return (vector, timing_stats) for a single query with cache + encode breakdown."""
    stats: dict[str, Any] = {
        "embed_query_method": "local",
        "embed_query_cache_hit": False,
        "embed_query_cache_lookup_ms": 0,
        "embed_query_encode_ms": 0,
        "embed_query_model": _tool_embed_model(settings),
    }
    if not _use_local_tool_embed(settings):
        stats["embed_query_method"] = "openai_fallback"
        from app.rag.embedding import get_embedding_timed

        vector, wall_ms = get_embedding_timed(text, settings, org_id=None)
        stats["embed_query_ms"] = wall_ms
        stats["embed_query_provider"] = "openai"
        return vector, stats

    model = _tool_embed_model(settings)
    key = _query_cache_key(model, text)
    ttl = _query_cache_ttl_sec(settings)
    now = time.monotonic()

    t_lookup = time.perf_counter()
    with _QUERY_CACHE_LOCK:
        cached = _QUERY_CACHE.get(key)
        if cached is not None and cached[0] > now:
            stats["embed_query_cache_hit"] = True
            stats["embed_query_cache_lookup_ms"] = int((time.perf_counter() - t_lookup) * 1000)
            stats["embed_query_ms"] = stats["embed_query_cache_lookup_ms"]
            stats["embed_query_provider"] = "local_cache"
            return list(cached[1]), stats
    stats["embed_query_cache_lookup_ms"] = int((time.perf_counter() - t_lookup) * 1000)

    t_encode = time.perf_counter()
    vector = embed_tool_retrieval_texts([text], settings)[0]
    encode_ms = int((time.perf_counter() - t_encode) * 1000)
    stats["embed_query_encode_ms"] = encode_ms
    stats["embed_query_ms"] = stats["embed_query_cache_lookup_ms"] + encode_ms
    stats["embed_query_provider"] = "local"

    with _QUERY_CACHE_LOCK:
        _QUERY_CACHE[key] = (now + ttl, list(vector))
    return vector, stats


def embed_tool_retrieval_docs_timed(
    texts: list[str],
    settings: Settings,
) -> tuple[list[list[float]], dict[str, Any]]:
    """Batch-encode tool documents locally; returns vectors + timing stats."""
    if not texts:
        return [], {"embed_tool_docs_ms": 0, "embed_tool_doc_provider": "local"}
    if not _use_local_tool_embed(settings):
        from app.rag.embedding import embed_texts_batch_openai

        t0 = time.perf_counter()
        vectors = embed_texts_batch_openai(texts, settings, org_id=None)
        return vectors, {
            "embed_tool_docs_ms": int((time.perf_counter() - t0) * 1000),
            "embed_tool_doc_provider": "openai",
            "embed_tool_doc_batch_api_calls": 1,
        }
    t0 = time.perf_counter()
    vectors = embed_tool_retrieval_texts(texts, settings)
    return vectors, {
        "embed_tool_docs_ms": int((time.perf_counter() - t0) * 1000),
        "embed_tool_doc_provider": "local",
        "embed_tool_doc_batch_api_calls": 0,
    }
