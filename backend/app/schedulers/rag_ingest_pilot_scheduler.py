"""Phase 2D: in-process RAG indexing pilot for named tenants only.

The standalone ingest worker (``scripts/ingest_worker.py``) has never run in
production, so queued ingest jobs wait forever. This pilot processes them inside
the API process, for the organisations in RAG_WORKER_PILOT_ORG_IDS only, with
hard bounds so it cannot crowd out chat and voice:

* one job at a time per replica, in a worker thread (never on the event loop);
* at most RAG_WORKER_PILOT_MAX_JOBS_PER_TICK jobs per tick, then a pause;
* the org must also opt in to customer context (source governance), checked
  per job and failing closed;
* unchanged documents are skipped by content checksum (see ``process_job``).

Off unless RAG_WORKER_PILOT_ENABLED is true and the org list is non-empty.
Needs migration 20261012024300 (``claim_rag_ingest_job_for_orgs``).
"""
from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any

from supabase import create_client

from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.services.ingestion_interlock import (
    ingestion_flag_configured,
    ingestion_flag_on,
    provider_lifecycle_supported,
)

logger = get_logger(__name__)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_INITIAL_DELAY_S = 60


def pilot_org_ids(settings: Any) -> list[str]:
    raw = str(getattr(settings, "rag_worker_pilot_org_ids", "") or "")
    return sorted({p.strip().lower() for p in raw.split(",") if _UUID_RE.match(p.strip())})


def _release_job(client: Any, job: dict[str, Any], reason: str) -> None:
    """Hand a claimed job back to the queue untouched (org not opted in)."""
    client.table("rag_ingest_jobs").update(
        {"status": "queued", "worker_id": None, "heartbeat_at": None}
    ).eq("id", str(job["id"])).eq("worker_id", str(job.get("worker_id") or "")).execute()
    logger.info("rag_pilot_job_released job_id=%s reason=%s", job.get("id"), reason)


def pilot_job_hold_reason(settings: Any, client: Any, job: dict[str, Any]) -> str | None:
    """Why a claimed job of a pilot org must not be indexed, or None to index it.

    Shared by the in-process pilot and the standalone worker (``app.rag.worker``), so
    pilot-scoped work gets the same interlock whichever process claims it:

    * the lifecycle interlock for RAG_WORKER_PILOT_ENABLED;
    * the source's provider must have a revoke call wired (Notion, Confluence,
      Zendesk, Workday sources are held);
    * the org must opt in to customer context for that source type.
    """
    from app.services.source_governance import customer_context_allowed_for_org

    if not ingestion_flag_on(settings, "rag_worker_pilot_enabled"):
        return "lifecycle_interlock"
    org_id = str(job.get("org_id") or "").lower()
    source_type = _source_type(client, job)
    if not provider_lifecycle_supported(source_type):
        return "provider_lifecycle_unsupported"
    if not customer_context_allowed_for_org(client, org_id, source_type):
        return "customer_context_not_opted_in"
    return None


def run_pilot_tick(settings: Settings, client: Any, worker_id: str) -> dict[str, int]:
    """Claim and process up to the per-tick limit. Synchronous; run in a thread."""
    from app.rag.worker import process_job

    orgs = pilot_org_ids(settings)
    out = {"processed": 0, "released": 0}
    if not orgs:
        return out
    limit = max(1, int(getattr(settings, "rag_worker_pilot_max_jobs_per_tick", 5) or 5))
    released: set[str] = set()
    for _ in range(limit):
        res = client.rpc(
            "claim_rag_ingest_job_for_orgs",
            {
                "p_worker_id": worker_id,
                "p_visibility_timeout_seconds": 300,
                "p_org_ids": [o for o in orgs if o not in released],
            },
        ).execute()
        rows = res.data or []
        job = rows if isinstance(rows, dict) else (rows[0] if rows else None)
        if not job:
            break
        org_id = str(job.get("org_id") or "").lower()
        reason = pilot_job_hold_reason(settings, client, job)
        if reason:
            # The org is left alone for the rest of this tick; claims are oldest-first,
            # so a held job at the head of an org's queue holds that org back (fail closed).
            _release_job(client, job, reason)
            released.add(org_id)
            out["released"] += 1
            if len(released) == len(orgs):
                break
            continue
        process_job(settings, client, job)
        out["processed"] += 1
    return out


def _source_type(client: Any, job: dict[str, Any]) -> str:
    try:
        res = (
            client.table("rag_sources")
            .select("type")
            .eq("id", str(job.get("source_id") or ""))
            .eq("org_id", str(job.get("org_id") or ""))
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return str((rows[0] if rows else {}).get("type") or "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag_pilot_source_lookup_failed job_id=%s error=%s", job.get("id"), exc)
        return ""


async def _loop(settings: Settings, interval: int) -> None:
    client = shared_service_client(settings, create_client)
    worker_id = f"rag-pilot-{uuid.uuid4().hex[:12]}"
    logger.info("rag_pilot started worker=%s orgs=%s interval=%ss", worker_id, pilot_org_ids(settings), interval)
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        try:
            disabled = bool(getattr(settings, "disable_ingestion", False))
            if not disabled and not ingestion_flag_on(settings, "rag_worker_pilot_enabled"):
                # Nothing is claimed while lifecycle cannot be proven; queued jobs stay queued.
                logger.warning("rag_pilot_tick_held reason=lifecycle_interlock")
            elif not disabled:
                result = await asyncio.to_thread(run_pilot_tick, settings, client, worker_id)
                if result["processed"] or result["released"]:
                    logger.info("rag_pilot_tick worker=%s %s", worker_id, result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rag_pilot_tick_failed error=%s", exc)
        await asyncio.sleep(interval)


def start_rag_ingest_pilot_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        # Configuration only at boot (the relay has not ticked yet); each tick checks runtime.
        enabled = ingestion_flag_configured(settings, "rag_worker_pilot_enabled")
        interval = int(getattr(settings, "rag_worker_pilot_interval_seconds", 30) or 0)
        orgs = pilot_org_ids(settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag pilot not started: %s", exc)
        return None
    if not enabled or interval <= 0 or not orgs:
        logger.info("rag ingest pilot disabled")
        return None
    return asyncio.create_task(_loop(settings, interval))


async def stop_rag_ingest_pilot_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag pilot stop error: %s", exc)
