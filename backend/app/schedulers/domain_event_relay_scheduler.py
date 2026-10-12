"""In-process relay tick for domain_event_outbox (Phase 2A).

Safe on every replica at once: events are claimed with SKIP LOCKED leases, so
replicas never take the same event while its lease holds. Off unless
DOMAIN_EVENT_RELAY_ENABLED is true.
"""
from __future__ import annotations

import asyncio
import time

from supabase import create_client

from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.services import lifecycle_runtime
from app.services.domain_events import (
    DomainEventRelay,
    domain_event_outbox_stats,
    prune_domain_events,
)

logger = get_logger(__name__)

_INITIAL_DELAY_S = 30
_PRUNE_EVERY_S = 3600
_STATS_EVERY_S = 300


async def _loop(settings: Settings, interval: int) -> None:
    client = shared_service_client(settings, create_client)
    relay = DomainEventRelay(
        client,
        batch_size=max(1, int(settings.domain_event_relay_batch_size or 50)),
        lease_seconds=max(10, int(settings.domain_event_relay_lease_seconds or 120)),
    )
    logger.info("domain_event_relay started worker=%s interval=%ss", relay.worker_id, interval)
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    last_prune = 0.0
    last_stats = 0.0
    last_probe = 0.0
    while True:
        try:
            started = time.monotonic()
            result = await asyncio.to_thread(relay.run_once)
            # Heartbeat for the ingestion interlock: a tick that claimed and settled.
            lifecycle_runtime.record_relay_tick(ok=True)
            if result.claimed:
                logger.info(
                    "domain_event_relay_tick worker=%s duration_ms=%s %s",
                    relay.worker_id,
                    int((time.monotonic() - started) * 1000),
                    result.as_dict(),
                )
            now = time.monotonic()
            if now - last_probe >= lifecycle_runtime.DB_PROBE_EVERY_S:
                last_probe = now
                probe = await asyncio.to_thread(lifecycle_runtime.probe_lifecycle_database, client)
                lifecycle_runtime.record_db_probe(probe)
                if not probe.get("ok"):
                    logger.warning("lifecycle_runtime_probe_failed %s", probe)
            if now - last_stats >= _STATS_EVERY_S:
                last_stats = now
                stats = await asyncio.to_thread(domain_event_outbox_stats, client)
                logger.info("domain_event_outbox_stats %s", stats)
            if now - last_prune >= _PRUNE_EVERY_S:
                last_prune = now
                pruned = await asyncio.to_thread(
                    prune_domain_events,
                    client,
                    retention_days=max(1, int(settings.domain_event_retention_days or 14)),
                )
                if pruned:
                    logger.info("domain_event_outbox_pruned rows=%s", pruned)
            # A full batch means more is due: go again without waiting.
            if result.claimed >= relay.batch_size:
                continue
        except Exception as exc:  # noqa: BLE001
            lifecycle_runtime.record_relay_tick(ok=False, error=f"{type(exc).__name__}: {exc}")
            logger.warning("domain_event_relay_tick_failed error=%s", exc)
        await asyncio.sleep(interval)


def start_domain_event_relay_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        enabled = bool(settings.domain_event_relay_enabled)
        interval = int(settings.domain_event_relay_interval_seconds or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("domain event relay not started: %s", exc)
        return None
    if not enabled:
        logger.info("domain event relay disabled (DOMAIN_EVENT_RELAY_ENABLED is false)")
        return None
    if interval <= 0:
        logger.info("domain event relay disabled (interval<=0)")
        return None
    from app.services.customer_observation_feed import register_customer_observation_handlers
    from app.services.outcome_learning_handler import register_outcome_learning_handlers
    from app.services.source_lifecycle import register_source_lifecycle_handlers

    register_source_lifecycle_handlers()
    register_customer_observation_handlers()
    # No-op unless OUTCOME_LEARNING_HANDLER_ENABLED is true.
    register_outcome_learning_handlers(settings)
    task = asyncio.create_task(_loop(settings, interval))
    lifecycle_runtime.relay_started(
        task,
        interval_s=interval,
        lease_s=max(10, int(getattr(settings, "domain_event_relay_lease_seconds", 120) or 120)),
    )
    return task


async def stop_domain_event_relay_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    lifecycle_runtime.relay_stopped()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("domain event relay stop error: %s", exc)
