"""Background cache warming for frequent org queries (embedding + retrieval caches).

Intentionally NOT migrated to Temporal: best-effort performance optimization;
a missed warm tick has no correctness impact.
"""
from __future__ import annotations

import asyncio

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.company_intelligence_collectors import get_active_org_ids
from app.services.rag_service import get_rag_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

_INITIAL_DELAY_S = 600
_TOP_QUERIES_PER_ORG = 5


async def _warm_org(org_id: str, settings: Settings) -> int:
    db = get_supabase_client(settings)
    clusters = (
        db.table("org_query_clusters")
        .select("representative_queries, query_count")
        .eq("org_id", org_id)
        .order("query_count", desc=True)
        .limit(10)
        .execute()
        .data
        or []
    )
    queries: list[str] = []
    for cluster in clusters:
        for text in cluster.get("representative_queries") or []:
            value = str(text or "").strip()
            if value and value not in queries:
                queries.append(value)
            if len(queries) >= _TOP_QUERIES_PER_ORG:
                break
        if len(queries) >= _TOP_QUERIES_PER_ORG:
            break

    if not queries:
        return 0

    rag = get_rag_service(settings)
    warmed = 0
    for query in queries:
        try:
            await rag.retrieve_hybrid_rows(
                org_id,
                query,
                scope="organization",
                top_k=settings.rag_top_k or 8,
                filters={"environment": "default"},
            )
            warmed += 1
        except Exception as exc:  # noqa: BLE001
            logger.debug("cache_warm_query_failed org_id=%s error=%s", org_id, exc)
    return warmed


async def _run_once(settings: Settings) -> None:
    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=10)
    total = 0
    for org_id in org_ids:
        try:
            total += await _warm_org(org_id, settings)
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache_warm_org_failed org_id=%s error=%s", org_id, exc)
    logger.info("cache_warming_tick orgs=%s queries_warmed=%s", len(org_ids), total)


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        await _run_once(settings)
        await asyncio.sleep(interval)


def start_cache_warming_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(getattr(settings, "cache_warming_interval_seconds", 3600) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache warming scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("cache warming scheduler disabled (CACHE_WARMING_INTERVAL_SECONDS<=0)")
        return None
    logger.info("cache warming scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_cache_warming_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache warming scheduler stop error: %s", exc)
