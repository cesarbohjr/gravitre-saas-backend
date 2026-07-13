"""Phase 1.5 — ONE durable cache_get / cache_set for all pack sources.

In-memory SourceCache remains an optional L1; durable rows in knowledge_pack_cache
are the source of truth for live evidence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.intelligence_packs.shared.cache import get_source_cache

logger = get_logger(__name__)


def cache_get(client: Any, *, vendor: str, cache_key: str) -> dict[str, Any] | None:
    """Return non-expired cache row as {id, payload, provenance, expires_at} or None."""
    v = str(vendor or "").strip().lower()
    key = str(cache_key or "").strip()
    if not v or not key:
        return None

    mem_key = f"{v}:{key}"
    mem = get_source_cache().get(mem_key)
    if isinstance(mem, dict) and "payload" in mem:
        return mem

    try:
        result = (
            client.table("knowledge_pack_cache")
            .select("id, vendor, cache_key, payload, provenance, expires_at, ttl_seconds")
            .eq("vendor", v)
            .eq("cache_key", key)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("knowledge_pack_cache_get_failed vendor=%s err=%s", v, exc)
        return None

    rows = result.data or []
    if not rows:
        return None
    row = rows[0]
    expires_at = row.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp <= datetime.now(timezone.utc):
                return None
        except ValueError:
            pass

    out = {
        "id": row["id"],
        "vendor": row["vendor"],
        "cache_key": row["cache_key"],
        "payload": row.get("payload"),
        "provenance": row.get("provenance") or {},
        "expires_at": expires_at,
        "ttl_seconds": row.get("ttl_seconds"),
    }
    get_source_cache().set(mem_key, out, ttl_seconds=int(row.get("ttl_seconds") or 60))
    return out


def cache_set(
    client: Any,
    *,
    vendor: str,
    cache_key: str,
    payload: Any,
    ttl_seconds: int,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Upsert durable cache row. Returns {id, vendor, cache_key, expires_at, ...}."""
    v = str(vendor or "").strip().lower()
    key = str(cache_key or "").strip()
    if not v or not key:
        raise ValueError("vendor and cache_key are required")

    ttl = max(1, int(ttl_seconds))
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl)
    row_id = str(uuid4())
    prov = dict(provenance or {})
    prov.setdefault("source", v)
    prov.setdefault("cached_at", now.isoformat())

    row = {
        "id": row_id,
        "vendor": v,
        "cache_key": key,
        "payload": payload,
        "provenance": prov,
        "ttl_seconds": ttl,
        "expires_at": expires_at.isoformat(),
        "updated_at": now.isoformat(),
    }

    try:
        existing = (
            client.table("knowledge_pack_cache")
            .select("id")
            .eq("vendor", v)
            .eq("cache_key", key)
            .limit(1)
            .execute()
        )
        existing_rows = existing.data or []
        if existing_rows:
            row_id = str(existing_rows[0]["id"])
            row["id"] = row_id
            client.table("knowledge_pack_cache").update(
                {
                    "payload": payload,
                    "provenance": prov,
                    "ttl_seconds": ttl,
                    "expires_at": expires_at.isoformat(),
                    "updated_at": now.isoformat(),
                }
            ).eq("id", row_id).execute()
        else:
            row["created_at"] = now.isoformat()
            client.table("knowledge_pack_cache").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("knowledge_pack_cache_set_failed vendor=%s err=%s", v, exc)
        raise

    out = {
        "id": row_id,
        "vendor": v,
        "cache_key": key,
        "payload": payload,
        "provenance": prov,
        "expires_at": expires_at.isoformat(),
        "ttl_seconds": ttl,
    }
    get_source_cache().set(f"{v}:{key}", out, ttl_seconds=ttl)
    return out
