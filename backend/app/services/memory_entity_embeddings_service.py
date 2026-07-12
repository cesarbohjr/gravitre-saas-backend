"""STA-316 — index/search Memory entity embeddings (opaque tokens only)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.core.logging import get_logger
from app.services.memory_opaque_tokens import (
    MemoryOpaqueTokenError,
    assert_provider_safe_token,
    opaque_alias_token,
    opaque_entity_token,
    redact_mention_for_digest,
    token_digest,
)

logger = get_logger(__name__)

TABLE = "org_memory_entity_embeddings"
DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_RETENTION_DAYS = 30


def _hmac_secret(settings: Settings) -> str:
    # Deployment secret — combined with org_id inside token material.
    return (
        getattr(settings, "supabase_jwt_secret", None)
        or getattr(settings, "supabase_service_role_key", None)
        or "gravitre-memory-dev-secret"
    )


def embed_opaque_token(token: str, settings: Settings, *, org_id: str | None = None) -> list[float]:
    """Embed only after opaque-token validation. OpenAI only (no Voyage failover)."""
    safe = assert_provider_safe_token(token)
    from app.rag.embedding import EMBEDDING_REQUEST_TIMEOUT_S, record_embedding_cost, _estimate_tokens
    from app.services.providers.openai_adapter import OpenAIAdapter

    if not (settings.openai_api_key or "").strip():
        raise RuntimeError("OPENAI_API_KEY is not configured for Memory embeddings")
    adapter = OpenAIAdapter(
        client_getter=lambda: None,
        api_key_getter=lambda: (settings.openai_api_key or "").strip(),
        timeout_s=EMBEDDING_REQUEST_TIMEOUT_S,
    )
    vector = adapter.embed(safe, model=DEFAULT_MODEL)
    if not vector or len(vector) != 1536:
        raise RuntimeError("memory embedding dimension mismatch")
    record_embedding_cost(settings, org_id, "openai", DEFAULT_MODEL, _estimate_tokens(safe))
    return [float(x) for x in vector]


def upsert_memory_embedding_row(
    client: Any,
    *,
    org_id: str,
    integration: str,
    entity_type: str,
    entity_id: str,
    token_kind: str,
    token: str,
    embedding: list[float],
    model_version: str = DEFAULT_MODEL,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> bool:
    digest = token_digest(token)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=max(1, retention_days))
    row = {
        "org_id": org_id,
        "integration": (integration or "").strip().lower(),
        "entity_type": (entity_type or "entity").strip(),
        "entity_id": str(entity_id).strip(),
        "token_kind": token_kind,
        "token_digest": digest,
        "embedding": embedding,
        "model_version": model_version,
        "token_version": "v1",
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }
    try:
        client.table(TABLE).upsert(
            row,
            on_conflict="org_id,integration,entity_type,entity_id,token_kind,token_digest,model_version",
        ).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_embedding_upsert_failed error=%s", str(exc)[:200])
        return False


async def index_entity_and_alias(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    integration: str,
    entity_type: str,
    entity_id: str,
    alias: str | None = None,
) -> int:
    """Index opaque entity token (+ optional opaque alias digest). Returns rows written."""
    secret = _hmac_secret(settings)
    written = 0
    entity_token = opaque_entity_token(
        org_id=org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        secret=secret,
    )
    entity_vec = embed_opaque_token(entity_token, settings, org_id=org_id)
    if upsert_memory_embedding_row(
        client,
        org_id=org_id,
        integration=integration,
        entity_type=entity_type,
        entity_id=entity_id,
        token_kind="entity",
        token=entity_token,
        embedding=entity_vec,
    ):
        written += 1

    alias_norm = redact_mention_for_digest(alias or "")
    if alias_norm:
        alias_token = opaque_alias_token(org_id=org_id, alias_normalized=alias_norm, secret=secret)
        alias_vec = embed_opaque_token(alias_token, settings, org_id=org_id)
        if upsert_memory_embedding_row(
            client,
            org_id=org_id,
            integration=integration,
            entity_type=entity_type,
            entity_id=entity_id,
            token_kind="alias",
            token=alias_token,
            embedding=alias_vec,
        ):
            written += 1
    return written


async def search_memory_by_mention(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    mention: str,
    integration: str | None = None,
    entity_type: str | None = None,
    match_count: int = 5,
    min_score: float = 0.92,
) -> list[dict[str, Any]]:
    """Embed HMAC(redacted mention) and search — never sends raw mention to provider."""
    secret = _hmac_secret(settings)
    alias_norm = redact_mention_for_digest(mention)
    if not alias_norm:
        return []
    query_token = opaque_alias_token(org_id=org_id, alias_normalized=alias_norm, secret=secret)
    try:
        query_vec = embed_opaque_token(query_token, settings, org_id=org_id)
    except MemoryOpaqueTokenError:
        return []

    try:
        result = client.rpc(
            "match_org_memory_entity_embeddings",
            {
                "p_org_id": org_id,
                "p_query_embedding": query_vec,
                "p_integration": (integration or None),
                "p_entity_type": (entity_type or None),
                "p_match_count": match_count,
                "p_min_score": min_score,
            },
        ).execute()
        return list(result.data or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_embedding_search_failed error=%s", str(exc)[:200])
        return []


def purge_org_memory_embeddings(client: Any, org_id: str, *, expired_only: bool = True) -> int:
    try:
        result = client.rpc(
            "purge_org_memory_entity_embeddings",
            {"p_org_id": org_id, "p_expired_only": expired_only},
        ).execute()
        return int(result.data or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_embedding_purge_failed error=%s", str(exc)[:200])
        return 0
