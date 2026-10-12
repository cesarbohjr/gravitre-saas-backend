"""Daily rule-based behaviour signals per account (Phase 7).

Calls ``compute_entity_behavior_signals`` (migration 20261012040000) for every
org with customer observations in the last 90 days. The function upserts one
row per entity, signal and day, so a second replica running the same tick only
rewrites the same values.

Off unless ENTITY_BEHAVIOR_SIGNALS_ENABLED is true; DISABLE_INGESTION skips the tick.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from supabase import create_client

from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger

logger = get_logger(__name__)

_INITIAL_DELAY_S = 600
LOOKBACK_DAYS = 90
# Upper bound on orgs discovered per tick; each org costs one indexed lookup.
MAX_ORGS_PER_TICK = 5000


def orgs_with_recent_observations(
    client: Any, *, now: datetime | None = None, max_orgs: int = MAX_ORGS_PER_TICK
) -> list[str]:
    """Distinct org ids with an observation in the lookback window, ascending.

    PostgREST has no DISTINCT, so this walks org ids in order: each request asks
    for the first org id greater than the last one found (``LIMIT 1``), which the
    ``(org_id, ...)`` index on entity_observations answers without reading every
    row of a busy org. One request per org plus one, never more than ``max_orgs``.
    """
    now = now or datetime.now(UTC)
    since = (now - timedelta(days=LOOKBACK_DAYS)).isoformat()
    found: list[str] = []
    last: str | None = None
    while len(found) < max_orgs:
        query = client.table("entity_observations").select("org_id").gte("observed_at", since)
        if last is not None:
            query = query.gt("org_id", last)
        rows = query.order("org_id").limit(1).execute().data or []
        org_id = str(rows[0].get("org_id") or "") if rows and isinstance(rows[0], dict) else ""
        if not org_id or org_id == last:
            break
        found.append(org_id)
        last = org_id
    else:
        logger.warning("behavior_signals_org_discovery_capped max_orgs=%s", max_orgs)
    return found


def run_behavior_signals(client: Any, *, now: datetime | None = None, settings: Any = None) -> dict[str, int]:
    """One pass over all orgs; returns rows written per org. Never raises per org.

    With ACCOUNT_PLAY_PROPOSALS_ENABLED, each org's at-risk accounts then get
    Play proposals (Phase 8) from the fresh signals.
    """
    from app.core.ingestion_kill_switch import ingestion_disabled
    from app.services.account_play_triggers import (
        account_play_proposals_enabled,
        run_account_play_proposals,
    )

    if settings is not None and ingestion_disabled(settings):
        logger.warning("behavior_signals_skipped reason=ingestion_disabled")
        return {}
    now = now or datetime.now(UTC)
    propose = settings is not None and account_play_proposals_enabled(settings)
    written: dict[str, int] = {}
    for org_id in orgs_with_recent_observations(client, now=now):
        try:
            res = client.rpc(
                "compute_entity_behavior_signals", {"p_org_id": org_id, "p_as_of": now.isoformat()}
            ).execute()
            written[org_id] = int(res.data or 0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("behavior_signals_org_failed org_id=%s error=%s", org_id, type(exc).__name__)
            continue
        if propose:
            proposals = run_account_play_proposals(client, settings, org_id, now=now)
            filed = sum(1 for p in proposals if p.get("status") == "proposed" and not p.get("deduplicated"))
            if filed:
                logger.info("account_play_proposals org_id=%s filed=%s", org_id, filed)
    return written


async def _loop(settings: Settings, interval: int) -> None:
    client = shared_service_client(settings, create_client)
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        try:
            written = await asyncio.to_thread(run_behavior_signals, client, settings=settings)
            logger.info("behavior_signals_tick orgs=%s rows=%s", len(written), sum(written.values()))
        except Exception as exc:  # noqa: BLE001
            logger.warning("behavior_signals_tick_failed error=%s", exc)
        await asyncio.sleep(interval)


def start_entity_behavior_signals_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        enabled = getattr(settings, "entity_behavior_signals_enabled", False) is True
        interval = int(getattr(settings, "entity_behavior_signals_interval_seconds", 86400) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("behavior signals not started: %s", exc)
        return None
    if not enabled or interval <= 0:
        logger.info("behavior signals disabled")
        return None
    return asyncio.create_task(_loop(settings, interval))


async def stop_entity_behavior_signals_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("behavior signals stop error: %s", exc)
