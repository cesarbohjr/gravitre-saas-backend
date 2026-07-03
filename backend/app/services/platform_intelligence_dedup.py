"""Cross-surface intelligence event deduplication."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

_DEDUP_CACHE: dict[str, datetime] = {}
_DEDUP_TTL_SECONDS = 300


def build_intelligence_dedup_key(
    org_id: str,
    surface: str,
    entity_type: str,
    entity_id: str,
    event_type: str,
) -> str:
    raw = f"{org_id}|{surface}|{entity_type}|{entity_id}|{event_type}"
    return hashlib.sha256(raw.encode()).hexdigest()


def should_skip_duplicate_event(dedup_key: str, *, ttl_seconds: int = _DEDUP_TTL_SECONDS) -> bool:
    now = datetime.now(timezone.utc)
    expired = [key for key, ts in _DEDUP_CACHE.items() if now - ts > timedelta(seconds=ttl_seconds)]
    for key in expired:
        _DEDUP_CACHE.pop(key, None)
    if dedup_key in _DEDUP_CACHE:
        return True
    _DEDUP_CACHE[dedup_key] = now
    return False


def dedupe_intelligence_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    for row in records:
        key = build_intelligence_dedup_key(
            str(row.get("org_id") or ""),
            str(row.get("surface") or "unknown"),
            str(row.get("entity_type") or "unknown"),
            str(row.get("entity_id") or row.get("id") or ""),
            str(row.get("event_type") or row.get("outcome_event") or "event"),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept
