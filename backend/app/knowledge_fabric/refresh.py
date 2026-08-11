"""Refresh cycles for platform knowledge packs by declared cadence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.knowledge_fabric.ingest import ingest_pack, register_all_sources
from app.knowledge_fabric.registry import PLATFORM_KNOWLEDGE_SOURCES

logger = get_logger(__name__)

# How stale before a refresh is due (ops defaults)
_CADENCE_MAX_AGE = {
    "realtime": timedelta(hours=6),
    "daily": timedelta(hours=26),
    "weekly": timedelta(days=8),
    "version_change": timedelta(days=7),
    "manual": None,
}


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def packs_due_for_refresh(client: Any, *, force: bool = False) -> list[str]:
    """Return pack_ids that should refresh now (excludes sales/marketing holds)."""
    register_all_sources(client)
    rows = (
        client.table("knowledge_sources")
        .select("source_id,refresh_frequency,last_refreshed_at,status,metadata")
        .eq("namespace", "platform_shared")
        .execute()
        .data
        or []
    )
    by_source = {r.get("source_id"): r for r in rows}
    due: set[str] = set()
    now = datetime.now(timezone.utc)
    for spec in PLATFORM_KNOWLEDGE_SOURCES:
        if spec.pack_id in {"pack.sales", "pack.marketing"}:
            continue
        if spec.hold_reason:
            continue
        if spec.license_type not in {"A", "B"}:
            continue
        row = by_source.get(spec.source_id) or {}
        if row.get("status") == "paused" and not force:
            continue
        max_age = _CADENCE_MAX_AGE.get(spec.refresh_frequency)
        if max_age is None and not force:
            continue
        last = _parse_ts(row.get("last_refreshed_at"))
        if force or last is None or (max_age and now - last >= max_age):
            due.add(spec.pack_id)
    return sorted(due)


async def run_refresh_cycle(
    client: Any,
    *,
    settings: Settings | None = None,
    force: bool = False,
    pack_ids: list[str] | None = None,
    limit: int = 4,
    embed: bool = True,
) -> dict[str, Any]:
    settings = settings or get_settings()
    targets = pack_ids or packs_due_for_refresh(client, force=force)
    targets = [p for p in targets if p not in {"pack.sales", "pack.marketing"}]
    started = datetime.now(timezone.utc).isoformat()
    results: dict[str, Any] = {}
    for pack_id in targets:
        before = (
            client.table("knowledge_sources")
            .select("source_id,last_refreshed_at")
            .contains("metadata", {"pack_id": pack_id})
            .execute()
        )
        # metadata contains filter may not work on all PostgREST — fallback scan
        before_map = {r["source_id"]: r.get("last_refreshed_at") for r in (before.data or [])}
        if not before_map:
            all_src = (
                client.table("knowledge_sources")
                .select("source_id,last_refreshed_at,metadata")
                .eq("namespace", "platform_shared")
                .execute()
                .data
                or []
            )
            before_map = {
                r["source_id"]: r.get("last_refreshed_at")
                for r in all_src
                if isinstance(r.get("metadata"), dict) and r["metadata"].get("pack_id") == pack_id
            }
        outcome = await ingest_pack(
            client,
            pack_id,
            settings=settings,
            embed=embed,
            limit=limit,
        )
        after = (
            client.table("knowledge_sources")
            .select("source_id,last_refreshed_at,metadata")
            .eq("namespace", "platform_shared")
            .execute()
            .data
            or []
        )
        after_map = {
            r["source_id"]: r.get("last_refreshed_at")
            for r in after
            if isinstance(r.get("metadata"), dict) and r["metadata"].get("pack_id") == pack_id
        }
        results[pack_id] = {
            "ingest": outcome,
            "last_refreshed_before": before_map,
            "last_refreshed_after": after_map,
            "timestamps_advanced": any(
                (after_map.get(sid) or "") != (before_map.get(sid) or "")
                for sid in set(before_map) | set(after_map)
            ),
        }
        logger.info(
            "knowledge_fabric.refresh_pack",
            extra={"pack_id": pack_id, "chunks": outcome.get("chunks")},
        )
    return {
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "force": force,
        "packs": targets,
        "results": results,
    }
