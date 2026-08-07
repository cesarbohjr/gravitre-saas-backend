"""Workday HR policy docs → department-scoped RAG sync (STA-61)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.connectors.workday import (
    WorkdayAPIError,
    get_policy_content_text,
    search_policy_content,
)
from app.connectors.workday_oauth import ensure_workday_session
from app.rag.ingest import create_ingest_job, create_source, get_source
from app.core.safe_dict import safe_normalize_stored_dict

logger = logging.getLogger(__name__)

WORKDAY_HR_NAMESPACE = "workday_hr"
STALE_SYNC_HOURS = 24


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_workday_sync_targets(connector: dict[str, Any]) -> list[dict[str, Any]]:
    config = connector.get("config") or {}
    targets = config.get("workday_sync_targets")
    return list(targets) if isinstance(targets, list) else []


def get_workday_sync_status(connector: dict[str, Any]) -> dict[str, Any]:
    config = connector.get("config") or {}
    last_synced = config.get("workday_last_synced_at")
    stale = False
    if last_synced:
        try:
            ts = datetime.fromisoformat(str(last_synced).replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            stale = age_hours >= STALE_SYNC_HOURS
        except ValueError:
            stale = True
    elif get_workday_sync_targets(connector):
        stale = True
    return {
        "targets": get_workday_sync_targets(connector),
        "rag_source_id": config.get("workday_rag_source_id"),
        "department_id": config.get("workday_department_id"),
        "namespace": WORKDAY_HR_NAMESPACE,
        "tenant_url": config.get("tenant_url"),
        "tenant": config.get("tenant"),
        "last_synced_at": last_synced,
        "stale": stale,
        "stale_threshold_hours": STALE_SYNC_HOURS,
    }


def set_workday_sync_config(
    client: Any,
    org_id: str,
    connector_id: str,
    *,
    targets: list[dict[str, Any]] | None = None,
    department_id: str | None = None,
) -> dict[str, Any]:
    row = (
        client.table("connectors")
        .select("config,name,environment")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise ValueError("Connector not found")
    connector = dict(row.data[0])
    config = safe_normalize_stored_dict(connector, key='config')
    if targets is not None:
        normalized: list[dict[str, Any]] = []
        for item in targets:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            normalized.append(
                {
                    "id": str(item["id"]),
                    "type": str(item.get("type") or "policy"),
                    "title": str(item.get("title") or item["id"]),
                }
            )
        config["workday_sync_targets"] = normalized
    if department_id is not None:
        if department_id:
            config["workday_department_id"] = str(department_id)
        else:
            config.pop("workday_department_id", None)
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return get_workday_sync_status({**connector, "config": config})


def ensure_workday_rag_source(
    client: Any,
    org_id: str,
    connector: dict[str, Any],
    settings: Settings,
    *,
    created_by: str,
) -> str:
    _ = settings
    config = safe_normalize_stored_dict(connector, key='config')
    existing = config.get("workday_rag_source_id")
    environment = str(connector.get("environment") or "production")
    department_id = config.get("workday_department_id")
    if existing and get_source(client, org_id, str(existing), environment_name=environment):
        return str(existing)

    tenant = config.get("tenant") or connector.get("name") or "Workday"
    source = create_source(
        client,
        org_id,
        title=f"Workday HR — {tenant}",
        type_="workday",
        metadata={
            "connector_id": connector.get("id"),
            "tenant_url": config.get("tenant_url"),
            "tenant": config.get("tenant"),
            "namespace": WORKDAY_HR_NAMESPACE,
        },
        created_by=created_by,
        environment_name=environment,
        department_id=str(department_id) if department_id else None,
    )
    source_id = str(source["id"])
    config["workday_rag_source_id"] = source_id
    client.table("connectors").update({"config": config}).eq("id", connector["id"]).eq("org_id", org_id).execute()
    return source_id


def search_workday_policy_content(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    query: str | None = None,
) -> list[dict[str, Any]]:
    token, _tenant_url, _tenant, api_base, err = ensure_workday_session(
        client, org_id, connector_id, settings
    )
    if err or not token or not api_base:
        raise ValueError(err or "Workday not connected")
    return search_policy_content(api_base, token, query=query)


def _queue_policy_ingest(
    client: Any,
    *,
    org_id: str,
    source_id: str,
    content_id: str,
    title: str,
    text: str,
    created_by: str,
    environment_name: str,
    updated_at: str | None,
) -> str:
    body = text.strip()
    if not body:
        body = f"(empty Workday policy content {content_id})"
    job = create_ingest_job(
        client,
        org_id,
        source_id,
        external_id=f"workday:policy:{content_id}",
        created_by=created_by,
        request_payload={
            "title": title,
            "external_id": f"workday:policy:{content_id}",
            "text": body,
            "metadata": {
                "namespace": WORKDAY_HR_NAMESPACE,
                "workday_content_id": content_id,
                "workday_content_updated_at": updated_at,
            },
        },
        environment_name=environment_name,
    )
    return str(job["id"])


def run_workday_sync(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    actor_id: str,
    full_sync: bool = False,
) -> dict[str, Any]:
    """Sync configured Workday HR policy sources into RAG ingest jobs."""
    _ = full_sync
    row = (
        client.table("connectors")
        .select("id,name,config,environment")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise ValueError("Connector not found")
    connector = dict(row.data[0])
    targets = get_workday_sync_targets(connector)
    if not targets:
        raise ValueError("No Workday sync targets configured")

    token, _tenant_url, _tenant, api_base, err = ensure_workday_session(
        client, org_id, connector_id, settings
    )
    if err or not token or not api_base:
        raise ValueError(err or "Workday not connected")

    source_id = ensure_workday_rag_source(client, org_id, connector, settings, created_by=actor_id)
    environment = str(connector.get("environment") or "production")

    job_ids: list[str] = []
    docs_synced = 0
    errors: list[str] = []

    for target in targets:
        content_id = str(target.get("id") or "")
        if not content_id:
            continue
        try:
            title, body, updated_at = get_policy_content_text(api_base, token, content_id)
            job_id = _queue_policy_ingest(
                client,
                org_id=org_id,
                source_id=source_id,
                content_id=content_id,
                title=title or str(target.get("title") or content_id),
                text=body,
                created_by=actor_id,
                environment_name=environment,
                updated_at=updated_at,
            )
            job_ids.append(job_id)
            docs_synced += 1
        except WorkdayAPIError as exc:
            errors.append(f"content {content_id}: {exc}")

    config = safe_normalize_stored_dict(connector, key='config')
    config["workday_last_synced_at"] = _now_iso()
    config["workday_rag_source_id"] = source_id
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()

    logger.info(
        "workday_sync_completed org_id=%s connector_id=%s docs=%s jobs=%s errors=%s",
        org_id,
        connector_id,
        docs_synced,
        len(job_ids),
        len(errors),
    )
    return {
        "source_id": source_id,
        "namespace": WORKDAY_HR_NAMESPACE,
        "docs_synced": docs_synced,
        "jobs_queued": len(job_ids),
        "job_ids": job_ids[:20],
        "errors": errors,
        "last_synced_at": config["workday_last_synced_at"],
    }
