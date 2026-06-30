"""Cache key helpers for RAG hybrid retrieval."""
from __future__ import annotations

import json
from typing import Any


RETRIEVAL_TTL_SECONDS = 300
EMBEDDING_TTL_SECONDS = 86400 * 7
SOURCE_SUMMARY_TTL_SECONDS = 3600


def retrieval_cache_parts(
    org_id: str,
    query: str,
    scope: str,
    top_k: int,
    filters: dict[str, Any] | None,
) -> tuple[str, ...]:
    payload = json.dumps(filters or {}, sort_keys=True, default=str)
    disable_rerank = bool((filters or {}).get("disable_rerank"))
    return (org_id, query.strip(), scope, str(top_k), payload, str(disable_rerank))


def source_summary_cache_parts(
    org_id: str,
    sources: list[dict[str, Any]],
    *,
    conflict_count: int,
    refined_query: str | None,
) -> tuple[str, ...]:
    source_ids = sorted(
        {
            str(row.get("document_id") or row.get("id") or "")
            for row in sources
            if row.get("document_id") or row.get("id")
        }
    )
    return (
        org_id,
        "|".join(source_ids),
        str(conflict_count),
        (refined_query or "").strip()[:500],
    )
