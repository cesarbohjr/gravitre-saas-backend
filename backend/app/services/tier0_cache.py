"""Tier 0 instant-answer cache with source staleness invalidation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.services.cache_service import get_cache_service
from app.services.query_normalization import normalize_query
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

TIER0_TTL_SECONDS = 3600


async def get_tier0_answer(
    settings: Any,
    *,
    org_id: str,
    query: str,
    client: Any | None = None,
) -> dict[str, Any] | None:
    normalized = normalize_query(query)
    if not normalized:
        return None
    cache = get_cache_service(settings)
    cached = await cache.get("tier0_answer", org_id, normalized)
    if not isinstance(cached, dict):
        return None
    if await is_cache_entry_stale(settings, cached, org_id, client=client):
        return None
    await cache.record_hit("tier0_answer")
    return cached


async def set_tier0_answer(
    settings: Any,
    *,
    org_id: str,
    query: str,
    answer: str,
    source_document_ids: list[str],
    confidence: dict[str, Any] | None = None,
    answer_explanation: str | None = None,
    ttl_seconds: int = TIER0_TTL_SECONDS,
) -> None:
    normalized = normalize_query(query)
    if not normalized or not (answer or "").strip():
        return
    cache = get_cache_service(settings)
    fingerprint = await _source_fingerprint(settings, org_id, source_document_ids)
    payload = {
        "answer": answer.strip(),
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "source_document_ids": source_document_ids,
        "source_fingerprint": fingerprint,
        "confidence": confidence or {},
        "answer_explanation": answer_explanation or "",
    }
    await cache.set("tier0_answer", payload, ttl_seconds, org_id, normalized)


async def is_cache_entry_stale(
    settings: Any,
    cached_entry: dict[str, Any],
    org_id: str,
    *,
    client: Any | None = None,
) -> bool:
    doc_ids = [str(value) for value in (cached_entry.get("source_document_ids") or []) if value]
    if not doc_ids:
        return False
    db = client or get_supabase_client(settings)
    try:
        rows = (
            db.table("rag_documents")
            .select("id, updated_at")
            .eq("org_id", org_id)
            .in_("id", doc_ids)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("tier0 staleness check skipped org_id=%s error=%s", org_id, exc)
        return False
    if not rows:
        return True
    current_fp = _fingerprint_from_rows(rows)
    cached_fp = str(cached_entry.get("source_fingerprint") or "")
    return bool(cached_fp and current_fp != cached_fp)


async def _source_fingerprint(settings: Any, org_id: str, document_ids: list[str]) -> str:
    if not document_ids:
        return ""
    db = get_supabase_client(settings)
    try:
        rows = (
            db.table("rag_documents")
            .select("id, updated_at")
            .eq("org_id", org_id)
            .in_("id", document_ids)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        return ""
    return _fingerprint_from_rows(rows)


def _fingerprint_from_rows(rows: list[dict[str, Any]]) -> str:
    parts = [
        f"{row.get('id')}:{row.get('updated_at') or ''}"
        for row in sorted(rows, key=lambda item: str(item.get("id") or ""))
    ]
    return "|".join(parts)
