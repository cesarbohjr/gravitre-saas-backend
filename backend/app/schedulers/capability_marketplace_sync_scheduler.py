"""Background sync for organization Git-backed capability marketplaces."""
from __future__ import annotations

import asyncio
import os

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client
from app.capabilities.github_sync import sync_public_github_marketplace
from app.capabilities.repository import update_marketplace_sync_status

logger = get_logger(__name__)

_DEFAULT_INTERVAL_S = 86_400
_INITIAL_DELAY_S = 600
_MAX_SOURCES_PER_TICK = 25


async def _sync_source(client, source: dict, settings: Settings) -> None:
    source_id = str(source.get("id") or "")
    org_id = str(source.get("org_id") or "")
    if not source_id or not org_id:
        return
    update_marketplace_sync_status(
        client,
        org_id=org_id,
        source_id=source_id,
        sync_status="syncing",
    )
    try:
        result = await sync_public_github_marketplace(
            client,
            org_id=org_id,
            user_id=str(source.get("created_by") or ""),
            source=source,
        )
    except Exception as exc:  # noqa: BLE001
        update_marketplace_sync_status(
            client,
            org_id=org_id,
            source_id=source_id,
            sync_status="failed",
            error=str(exc),
        )
        logger.warning(
            "capability_marketplace_auto_sync_failed org_id=%s source_id=%s error=%s",
            org_id,
            source_id,
            exc,
        )
        return
    update_marketplace_sync_status(
        client,
        org_id=org_id,
        source_id=source_id,
        sync_status="completed",
        synced=True,
    )
    logger.info(
        "capability_marketplace_auto_sync_completed org_id=%s source_id=%s discovered=%s ingested=%s",
        org_id,
        source_id,
        result.get("discovered"),
        result.get("ingested"),
    )


async def _run_once(settings: Settings) -> None:
    client = get_supabase_client(settings)
    response = (
        client.table("capability_marketplace_sources")
        .select("*")
        .eq("status", "active")
        .eq("auto_sync", True)
        .order("updated_at")
        .limit(_MAX_SOURCES_PER_TICK)
        .execute()
    )
    sources = list(response.data or [])
    for source in sources:
        await _sync_source(client, source, settings)


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        await _run_once(settings)
        await asyncio.sleep(interval)


def start_capability_marketplace_sync_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(
            os.environ.get(
                "CAPABILITY_MARKETPLACE_SYNC_INTERVAL_SECONDS",
                str(_DEFAULT_INTERVAL_S),
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("capability marketplace sync scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("capability marketplace sync scheduler disabled")
        return None
    logger.info("capability marketplace sync scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_capability_marketplace_sync_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("capability marketplace sync scheduler stop error: %s", exc)
