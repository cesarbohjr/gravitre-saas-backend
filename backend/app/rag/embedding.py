"""BE-10: Embedding client with provider failover (OpenAI -> Voyage).

Note on dimensions: the pgvector column is sized for OpenAI text-embedding-3-small
(1536 dims). Voyage (voyage-3, 1024 dims) is NOT dimension-compatible with an
OpenAI-indexed corpus, so the Voyage fallback is only semantically valid if the
corpus is (re)indexed with Voyage. For querying an OpenAI-indexed corpus, a Voyage
vector will fail the vector search and the caller falls back to keyword search.
"""
from __future__ import annotations

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

EMBEDDING_REQUEST_TIMEOUT_S = 30.0


def embed_with_failover(text: str, settings: Settings) -> tuple[list[float], str]:
    """Return (embedding_vector, method) trying OpenAI then Voyage.

    method is one of: "openai" | "voyage". Raises ValueError if no provider is
    configured or all configured providers fail.
    """
    # Imported lazily to avoid an app.services <-> app.rag import cycle.
    from app.services.providers.anthropic_adapter import AnthropicAdapter
    from app.services.providers.openai_adapter import OpenAIAdapter

    errors: list[str] = []

    # 1) OpenAI (primary)
    if (settings.openai_api_key or "").strip():
        try:
            adapter = OpenAIAdapter(
                client_getter=lambda: None,
                api_key_getter=lambda: (settings.openai_api_key or "").strip(),
                timeout_s=EMBEDDING_REQUEST_TIMEOUT_S,
            )
            vector = adapter.embed(text, settings.embedding_model)
            return vector, "openai"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"openai: {exc}")
            logger.warning("embedding openai failed, trying voyage: %s", str(exc))

    # 2) Voyage (fallback, Anthropic ecosystem)
    voyage_key = (getattr(settings, "voyage_api_key", "") or "").strip()
    if voyage_key:
        try:
            adapter = AnthropicAdapter(
                api_key_getter=lambda: "",
                voyage_key_getter=lambda: voyage_key,
                timeout_s=EMBEDDING_REQUEST_TIMEOUT_S,
            )
            vector = adapter.embed(text, "voyage-3")
            return vector, "voyage"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"voyage: {exc}")
            logger.warning("embedding voyage failed: %s", str(exc))

    raise ValueError(f"No embedding provider available ({'; '.join(errors) or 'none configured'})")


def get_embedding(text: str, settings: Settings) -> list[float]:
    """Return embedding vector for text (OpenAI primary, Voyage fallback)."""
    vector, _method = embed_with_failover(text, settings)
    return vector
