"""STA-45: Unified knowledge sync scheduler (Notion → RAG v1)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.config import Settings
from app.services.hubspot_knowledge_sync_service import (
    hubspot_knowledge_sync_enabled,
    run_hubspot_knowledge_sync,
)
from app.services.notion_sync_service import get_notion_sync_targets, run_notion_sync
from app.services.zendesk_knowledge_sync_service import (
    run_zendesk_knowledge_sync,
    zendesk_knowledge_sync_enabled,
)
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

_SYNC_INTERVAL_RE = re.compile(r"^(\d+)\s*(h|hr|hour|hours|d|day|days|w|week|weeks)$", re.I)

SOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    "notion": {
        "targets_key": "notion_sync_targets",
        "last_synced_key": "notion_last_synced_at",
        "runner": "notion",
    },
    "hubspot": {
        "last_synced_key": "hubspot_last_synced_at",
        "runner": "hubspot",
        "skip_targets_check": True,
    },
    "zendesk": {
        "last_synced_key": "zendesk_last_synced_at",
        "runner": "zendesk",
        "skip_targets_check": True,
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def parse_sync_interval(sync_frequency: str | None) -> timedelta:
    """Map connector sync_frequency (e.g. 1h, 24h, daily) to timedelta."""
    raw = (sync_frequency or "24h").strip().lower()
    if raw in {"daily", "day"}:
        return timedelta(hours=24)
    if raw in {"weekly", "week"}:
        return timedelta(days=7)
    match = _SYNC_INTERVAL_RE.match(raw.replace(" ", ""))
    if not match:
        return timedelta(hours=24)
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("h"):
        return timedelta(hours=max(1, amount))
    if unit.startswith("d"):
        return timedelta(days=max(1, amount))
    return timedelta(weeks=max(1, amount))


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def connector_is_due(connector: dict[str, Any], *, now: datetime | None = None) -> bool:
    """True when sync_frequency elapsed since last sync."""
    now = now or _now()
    config = connector.get("config") or {}
    vendor = str(connector.get("type") or connector.get("vendor") or "").lower()
    spec = SOURCE_REGISTRY.get(vendor)
    if not spec:
        return False
    if vendor == "hubspot" and not hubspot_knowledge_sync_enabled(connector):
        return False
    if vendor == "zendesk" and not zendesk_knowledge_sync_enabled(connector):
        return False
    if not spec.get("skip_targets_check"):
        targets_key = spec.get("targets_key")
        if not targets_key:
            return False
        targets = config.get(targets_key) or []
        if not isinstance(targets, list) or not targets:
            return False

    last = _parse_ts(config.get(spec["last_synced_key"])) or _parse_ts(
        connector.get("last_sync_at") or connector.get("last_synced_at")
    )
    if not last:
        return True
    interval = parse_sync_interval(connector.get("sync_frequency"))
    return now >= last + interval


def list_due_knowledge_connectors(client: Any, *, environment: str | None = None) -> list[dict[str, Any]]:
    query = (
        client.table("connectors")
        .select("id,org_id,type,vendor,status,config,environment,sync_frequency,last_sync_at")
        .in_("type", list(SOURCE_REGISTRY.keys()))
        .eq("status", "active")
        .is_("deleted_at", "null")
    )
    if environment:
        query = query.eq("environment", environment)
    result = query.execute()
    rows = [dict(r) for r in (result.data or [])]
    return [row for row in rows if connector_is_due(row)]


def create_knowledge_sync_job(
    client: Any,
    *,
    org_id: str,
    connector_id: str,
    source_type: str,
    trigger_type: str,
    environment_name: str,
    created_by: str | None = None,
    status: str = "queued",
) -> dict[str, Any]:
    row = {
        "org_id": org_id,
        "connector_id": connector_id,
        "source_type": source_type,
        "environment": environment_name,
        "status": status,
        "trigger_type": trigger_type,
        "scheduled_at": _now_iso(),
        "created_by": created_by,
    }
    if status == "running":
        row["started_at"] = _now_iso()
    inserted = client.table("knowledge_sync_jobs").insert(row).execute()
    if not inserted.data:
        raise RuntimeError("knowledge_sync_jobs insert failed")
    return dict(inserted.data[0])


def _update_knowledge_sync_job(client: Any, job_id: str, payload: dict[str, Any]) -> None:
    client.table("knowledge_sync_jobs").update(payload).eq("id", job_id).execute()


def _update_connector_after_sync(
    client: Any,
    org_id: str,
    connector_id: str,
    *,
    pages_synced: int,
    ingest_jobs_queued: int,
    source_type: str,
    last_synced_at: str,
) -> None:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        return
    config = dict(row.data[0].get("config") or {})
    spec = SOURCE_REGISTRY.get(source_type) or {}
    last_key = spec.get("last_synced_key")
    if last_key:
        config[last_key] = last_synced_at
    client.table("connectors").update(
        {
            "config": config,
            "last_synced_at": last_synced_at,
            "records_synced": int(pages_synced),
            "status": "active",
        }
    ).eq("id", connector_id).eq("org_id", org_id).execute()


def _run_notion_sync(
    client: Any,
    settings: Settings,
    connector: dict[str, Any],
    *,
    actor_id: str,
    full_sync: bool = False,
) -> dict[str, Any]:
    return run_notion_sync(
        client,
        str(connector["org_id"]),
        str(connector["id"]),
        settings,
        actor_id=actor_id,
        full_sync=full_sync,
    )


def _run_hubspot_sync(
    client: Any,
    settings: Settings,
    connector: dict[str, Any],
    *,
    actor_id: str,
    full_sync: bool = False,
) -> dict[str, Any]:
    return run_hubspot_knowledge_sync(
        client,
        str(connector["org_id"]),
        str(connector["id"]),
        settings,
        actor_id=actor_id,
        full_sync=full_sync,
    )


def _run_zendesk_sync(
    client: Any,
    settings: Settings,
    connector: dict[str, Any],
    *,
    actor_id: str,
    full_sync: bool = False,
) -> dict[str, Any]:
    return run_zendesk_knowledge_sync(
        client,
        str(connector["org_id"]),
        str(connector["id"]),
        settings,
        actor_id=actor_id,
        full_sync=full_sync,
    )


_RUNNERS: dict[str, Callable[..., dict[str, Any]]] = {
    "notion": _run_notion_sync,
    "hubspot": _run_hubspot_sync,
    "zendesk": _run_zendesk_sync,
}


def execute_knowledge_sync_job(
    client: Any,
    settings: Settings,
    job: dict[str, Any],
    connector: dict[str, Any],
    *,
    actor_id: str,
    full_sync: bool = False,
) -> dict[str, Any]:
    """Run one knowledge sync job; returns result summary."""
    job_id = str(job["id"])
    org_id = str(job["org_id"])
    connector_id = str(connector["id"])
    source_type = str(job.get("source_type") or connector.get("type") or "").lower()

    _update_knowledge_sync_job(
        client,
        job_id,
        {"status": "running", "started_at": _now_iso()},
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action="knowledge.sync.started",
        resource_type="knowledge_sync_job",
        resource_id=job_id,
        metadata={
            "connector_id": connector_id,
            "source_type": source_type,
            "trigger_type": job.get("trigger_type"),
        },
    )

    try:
        runner = _RUNNERS.get(source_type)
        if not runner:
            raise ValueError(f"Unsupported knowledge source: {source_type}")
        if source_type == "notion" and not get_notion_sync_targets(connector):
            raise ValueError("No Notion sync targets configured")
        if source_type == "hubspot" and not hubspot_knowledge_sync_enabled(connector):
            raise ValueError("HubSpot knowledge sync is disabled")
        if source_type == "zendesk" and not zendesk_knowledge_sync_enabled(connector):
            raise ValueError("Zendesk knowledge sync is disabled")

        result = runner(client, settings, connector, actor_id=actor_id, full_sync=full_sync)
        pages = int(result.get("pages_synced") or 0)
        queued = int(result.get("jobs_queued") or 0)
        last_synced = str(result.get("last_synced_at") or _now_iso())

        _update_connector_after_sync(
            client,
            org_id,
            connector_id,
            pages_synced=pages,
            ingest_jobs_queued=queued,
            source_type=source_type,
            last_synced_at=last_synced,
        )
        _update_knowledge_sync_job(
            client,
            job_id,
            {
                "status": "completed",
                "completed_at": _now_iso(),
                "pages_synced": pages,
                "ingest_jobs_queued": queued,
                "chunks_added": 0,
                "result": result,
                "error_message": None,
            },
        )
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id,
            action="knowledge.sync.completed",
            resource_type="knowledge_sync_job",
            resource_id=job_id,
            metadata={
                "connector_id": connector_id,
                "source_type": source_type,
                "pages_synced": pages,
                "ingest_jobs_queued": queued,
            },
        )
        return result
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)[:500]
        _update_knowledge_sync_job(
            client,
            job_id,
            {
                "status": "failed",
                "completed_at": _now_iso(),
                "error_message": msg,
            },
        )
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id,
            action="knowledge.sync.failed",
            resource_type="knowledge_sync_job",
            resource_id=job_id,
            metadata={"connector_id": connector_id, "source_type": source_type, "error": msg},
        )
        raise


def run_scheduled_knowledge_syncs(
    settings: Settings,
    *,
    client: Any | None = None,
    actor_id: str = "system",
) -> dict[str, Any]:
    """Process all connectors due for scheduled knowledge sync."""
    from supabase import create_client

    client = client or create_client(settings.supabase_url, settings.supabase_service_role_key)
    due = list_due_knowledge_connectors(client)
    outcomes: list[dict[str, Any]] = []

    for connector in due:
        org_id = str(connector["org_id"])
        connector_id = str(connector["id"])
        source_type = str(connector.get("type") or "").lower()
        env = str(connector.get("environment") or "production")
        job = create_knowledge_sync_job(
            client,
            org_id=org_id,
            connector_id=connector_id,
            source_type=source_type,
            trigger_type="schedule",
            environment_name=env,
            created_by=None,
        )
        try:
            result = execute_knowledge_sync_job(
                client,
                settings,
                job,
                connector,
                actor_id=actor_id,
            )
            outcomes.append(
                {
                    "connector_id": connector_id,
                    "job_id": str(job["id"]),
                    "status": "completed",
                    "pages_synced": result.get("pages_synced"),
                    "ingest_jobs_queued": result.get("jobs_queued"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "knowledge_sync_failed connector_id=%s error=%s",
                connector_id,
                exc,
            )
            outcomes.append(
                {
                    "connector_id": connector_id,
                    "job_id": str(job["id"]),
                    "status": "failed",
                    "error": str(exc)[:200],
                }
            )

    return {"due_count": len(due), "processed": len(outcomes), "outcomes": outcomes}


def trigger_connector_knowledge_sync(
    client: Any,
    settings: Settings,
    org_id: str,
    connector_id: str,
    *,
    actor_id: str,
    trigger_type: str = "manual",
    full_sync: bool = False,
) -> dict[str, Any]:
    row = (
        client.table("connectors")
        .select("id,org_id,type,vendor,status,config,environment,sync_frequency,last_sync_at")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not row.data:
        raise ValueError("Connector not found")
    connector = dict(row.data[0])
    source_type = str(connector.get("type") or "").lower()
    if source_type not in SOURCE_REGISTRY:
        raise ValueError(f"Connector type {source_type} does not support knowledge sync")

    job = create_knowledge_sync_job(
        client,
        org_id=org_id,
        connector_id=connector_id,
        source_type=source_type,
        trigger_type=trigger_type,
        environment_name=str(connector.get("environment") or "production"),
        created_by=actor_id if actor_id != "system" else None,
        status="queued",
    )
    return execute_knowledge_sync_job(
        client,
        settings,
        job,
        connector,
        actor_id=actor_id,
        full_sync=full_sync,
    )


def list_recent_sync_jobs(
    client: Any,
    org_id: str,
    *,
    limit: int = 25,
    connector_id: str | None = None,
) -> list[dict[str, Any]]:
    query = (
        client.table("knowledge_sync_jobs")
        .select(
            "id,connector_id,source_type,status,trigger_type,scheduled_at,started_at,"
            "completed_at,pages_synced,ingest_jobs_queued,chunks_added,error_message,created_at"
        )
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .limit(max(1, min(int(limit), 100)))
    )
    if connector_id:
        query = query.eq("connector_id", connector_id)
    result = query.execute()
    return list(result.data or [])
