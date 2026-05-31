"""BE-10: Embedding client with provider failover (OpenAI -> Voyage) + cost tracking.

Note on dimensions: the pgvector column is sized for OpenAI text-embedding-3-small
(1536 dims). Voyage (voyage-3, 1024 dims) is NOT dimension-compatible with an
OpenAI-indexed corpus unless the corpus is re-indexed (see docs/voyage-reindex-runbook.md).
When VOYAGE_EMBEDDING_ENABLED=false (default), Voyage is skipped entirely in the
failover chain.
"""
from __future__ import annotations

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

EMBEDDING_REQUEST_TIMEOUT_S = 30.0
OPENAI_CORPUS_DIMENSION = 1536
VOYAGE_EMBEDDING_DIMENSION = 1024

# Per-1K-token embedding pricing by method.
_EMBEDDING_RATE_PER_1K: dict[str, float] = {
    "openai": 0.00002,   # text-embedding-3-small: $0.02 / 1M
    "voyage": 0.00006,   # voyage-3: ~$0.06 / 1M (approx)
}


class EmbeddingDimensionMismatchError(ValueError):
    """Raised when Voyage embeddings cannot be used against the current corpus."""


def _estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def _voyage_enabled(settings: Settings) -> bool:
    """Single source of truth for whether Voyage is eligible in the failover chain."""
    return bool(getattr(settings, "voyage_embedding_enabled", False))


def _tag_langfuse_degradation(reason: str) -> None:
    """Best-effort Langfuse span tags when the SDK is configured."""
    try:
        from langfuse.decorators import langfuse_context  # type: ignore[import-untyped]

        langfuse_context.update_current_trace(
            metadata={"rag.embedding_degraded": True, "rag.degradation_reason": reason}
        )
    except Exception:  # noqa: BLE001
        return


def record_embedding_cost(
    settings: Settings,
    org_id: str | None,
    method: str,
    model: str,
    token_count: int,
) -> None:
    """Best-effort: write an embedding cost row to model_calls. No-op without org_id."""
    if not org_id or token_count <= 0:
        return
    rate = _EMBEDDING_RATE_PER_1K.get(method, _EMBEDDING_RATE_PER_1K["openai"])
    cost_usd = round(token_count * rate / 1000, 6)
    try:
        from app.workflows.repository import get_supabase_client

        client = get_supabase_client(settings)
        client.table("model_calls").insert(
            {
                "org_id": org_id,
                "task_type": "embedding",
                "provider": "openai" if method == "openai" else method,
                "model_name": model,
                "input_tokens": token_count,
                "output_tokens": 0,
                "cost_usd": cost_usd,
                "cache_hit": False,
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding cost record failed org_id=%s error=%s", org_id, str(exc))


def embed_with_failover(
    text: str,
    settings: Settings,
    org_id: str | None = None,
) -> tuple[list[float], str]:
    """Return (embedding_vector, method) trying OpenAI then Voyage (when enabled).

    method is one of: "openai" | "voyage". Raises ValueError if no provider is
    configured or all configured providers fail. Raises EmbeddingDimensionMismatchError
    when Voyage is enabled but the corpus dimension is incompatible.
    """
    from app.services.providers.anthropic_adapter import AnthropicAdapter
    from app.services.providers.openai_adapter import OpenAIAdapter

    errors: list[str] = []

    if (settings.openai_api_key or "").strip():
        try:
            adapter = OpenAIAdapter(
                client_getter=lambda: None,
                api_key_getter=lambda: (settings.openai_api_key or "").strip(),
                timeout_s=EMBEDDING_REQUEST_TIMEOUT_S,
            )
            vector = adapter.embed(text, settings.embedding_model)
            record_embedding_cost(settings, org_id, "openai", settings.embedding_model, _estimate_tokens(text))
            return vector, "openai"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"openai: {exc}")
            logger.warning("embedding openai failed, trying voyage: %s", str(exc))

    voyage_key = (getattr(settings, "voyage_api_key", "") or "").strip()
    if not _voyage_enabled(settings):
        if voyage_key:
            errors.append("voyage: disabled (VOYAGE_EMBEDDING_ENABLED=false)")
    elif voyage_key:
        corpus_dim = int(getattr(settings, "openai_embedding_dimension", OPENAI_CORPUS_DIMENSION) or OPENAI_CORPUS_DIMENSION)
        if corpus_dim != VOYAGE_EMBEDDING_DIMENSION:
            msg = (
                f"Voyage embedding dimension mismatch: corpus is {corpus_dim}-dim, "
                f"Voyage returns {VOYAGE_EMBEDDING_DIMENSION}-dim. Falling back to keyword search. "
                "Semantic quality will be degraded. Re-index corpus with Voyage to fix."
            )
            logger.warning(msg)
            _tag_langfuse_degradation("voyage_dimension_mismatch")
            raise EmbeddingDimensionMismatchError(msg)
        try:
            adapter = AnthropicAdapter(
                api_key_getter=lambda: "",
                voyage_key_getter=lambda: voyage_key,
                timeout_s=EMBEDDING_REQUEST_TIMEOUT_S,
            )
            vector = adapter.embed(text, "voyage-3")
            record_embedding_cost(settings, org_id, "voyage", "voyage-3", _estimate_tokens(text))
            return vector, "voyage"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"voyage: {exc}")
            logger.warning("embedding voyage failed: %s", str(exc))

    raise ValueError(f"No embedding provider available ({'; '.join(errors) or 'none configured'})")


def get_embedding(text: str, settings: Settings, org_id: str | None = None) -> list[float]:
    """Return embedding vector for text (OpenAI primary, Voyage when enabled)."""
    vector, _method = embed_with_failover(text, settings, org_id=org_id)
    return vector
