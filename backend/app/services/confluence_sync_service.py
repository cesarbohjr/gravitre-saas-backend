"""Confluence spaces → department-scoped RAG sync (STA-44)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.connectors.confluence import (
    ConfluenceAPIError,
    get_page_view_text,
    list_space_pages,
    search_spaces,
)
from app.connectors.confluence_oauth import ensure_confluence_session
from app.rag.ingest import create_ingest_job, create_source, get_source

logger = logging.getLogger(__name__)

STALE_SYNC_HOURS = 24


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_confluence_sync_targets(connector: dict[str, Any]) -> list[dict[str, Any]]:
    config = connector.get("config") or {}
    targets = config.get("confluence_sync_targets")
    return list(targets) if isinstance(targets, list) else []


def get_confluence_sync_status(connector: dict[str, Any]) -> dict[str, Any]:
    config = connector.get("config") or {}
    last_synced = config.get("confluence_last_synced_at")
    stale = False
    if last_synced:
        try:
            ts = datetime.fromisoformat(str(last_synced).replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            stale = age_hours >= STALE_SYNC_HOURS
        except ValueError:
            stale = True
    elif get_confluence_sync_targets(connector):
        stale = True
    return {
        "targets": get_confluence_sync_targets(connector),
        "rag_source_id": config.get("confluence_rag_source_id"),
        "department_id": config.get("confluence_department_id"),
        "cloud_id": config.get("cloud_id"),
        "site_name": config.get("site_name"),
        "site_url": config.get("site_url"),
        "last_synced_at": last_synced,
        "stale": stale,
        "stale_threshold_hours": STALE_SYNC_HOURS,
    }


def set_confluence_sync_config(
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
    config = dict(connector.get("config") or {})
    if targets is not None:
        normalized: list[dict[str, Any]] = []
        for item in targets:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            normalized.append(
                {
                    "id": str(item["id"]),
                    "type": str(item.get("type") or "space"),
                    "title": str(item.get("title") or item.get("key") or item["id"]),
                    "key": str(item.get("key") or ""),
                }
            )
        config["confluence_sync_targets"] = normalized
    if department_id is not None:
        if department_id:
            config["confluence_department_id"] = str(department_id)
        else:
            config.pop("confluence_department_id", None)
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return get_confluence_sync_status({**connector, "config": config})


def ensure_confluence_rag_source(
    client: Any,
    org_id: str,
    connector: dict[str, Any],
    settings: Settings,
    *,
    created_by: str,
) -> str:
    _ = settings
    config = dict(connector.get("config") or {})
    existing = config.get("confluence_rag_source_id")
    environment = str(connector.get("environment") or "production")
    department_id = config.get("confluence_department_id")
    if existing and get_source(client, org_id, str(existing), environment_name=environment):
        return str(existing)

    site = config.get("site_name") or connector.get("name") or "Confluence"
    source = create_source(
        client,
        org_id,
        title=f"Confluence — {site}",
        type_="confluence",
        metadata={"connector_id": connector.get("id"), "cloud_id": config.get("cloud_id")},
        created_by=created_by,
        environment_name=environment,
        department_id=str(department_id) if department_id else None,
    )
    source_id = str(source["id"])
    config["confluence_rag_source_id"] = source_id
    client.table("connectors").update({"config": config}).eq("id", connector["id"]).eq("org_id", org_id).execute()
    return source_id


def search_confluence_spaces(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    query: str | None = None,
) -> list[dict[str, Any]]:
    token, cloud_id, err = ensure_confluence_session(client, org_id, connector_id, settings)
    if err or not token or not cloud_id:
        raise ValueError(err or "Confluence not connected")
    return search_spaces(token, cloud_id, query=query)


def _queue_page_ingest(
    client: Any,
    *,
    org_id: str,
    source_id: str,
    page_id: str,
    title: str,
    text: str,
    created_by: str,
    environment_name: str,
    space_id: str,
    version_created_at: str | None,
) -> str:
    body = text.strip()
    if not body:
        body = f"(empty Confluence page {page_id})"
    job = create_ingest_job(
        client,
        org_id,
        source_id,
        external_id=f"confluence:page:{page_id}",
        created_by=created_by,
        request_payload={
            "title": title,
            "external_id": f"confluence:page:{page_id}",
            "text": body,
            "metadata": {
                "confluence_page_id": page_id,
                "confluence_space_id": space_id,
                "confluence_version_created_at": version_created_at,
            },
        },
        environment_name=environment_name,
    )
    return str(job["id"])


def run_confluence_sync(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    actor_id: str,
    full_sync: bool = False,
) -> dict[str, Any]:
    """Sync configured Confluence spaces into RAG ingest jobs."""
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
    targets = get_confluence_sync_targets(connector)
    if not targets:
        raise ValueError("No Confluence sync targets configured")

    token, cloud_id, err = ensure_confluence_session(client, org_id, connector_id, settings)
    if err or not token or not cloud_id:
        raise ValueError(err or "Confluence not connected")

    source_id = ensure_confluence_rag_source(client, org_id, connector, settings, created_by=actor_id)
    environment = str(connector.get("environment") or "production")

    job_ids: list[str] = []
    pages_synced = 0
    errors: list[str] = []

    for target in targets:
        space_id = str(target.get("id") or "")
        if not space_id:
            continue
        try:
            pages = list_space_pages(token, cloud_id, space_id)
        except ConfluenceAPIError as exc:
            errors.append(f"space {space_id}: {exc}")
            continue

        for page in pages:
            page_id = str(page.get("id") or "")
            if not page_id:
                continue
            try:
                title, body, version_created_at = get_page_view_text(token, cloud_id, page_id)
                job_id = _queue_page_ingest(
                    client,
                    org_id=org_id,
                    source_id=source_id,
                    page_id=page_id,
                    title=title or str(page.get("title") or page_id),
                    text=body,
                    created_by=actor_id,
                    environment_name=environment,
                    space_id=space_id,
                    version_created_at=version_created_at,
                )
                job_ids.append(job_id)
                pages_synced += 1
            except ConfluenceAPIError as exc:
                errors.append(f"page {page_id}: {exc}")

    config = dict(connector.get("config") or {})
    config["confluence_last_synced_at"] = _now_iso()
    config["confluence_rag_source_id"] = source_id
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()

    logger.info(
        "confluence_sync_completed org_id=%s connector_id=%s pages=%s jobs=%s errors=%s",
        org_id,
        connector_id,
        pages_synced,
        len(job_ids),
        len(errors),
    )
    return {
        "source_id": source_id,
        "pages_synced": pages_synced,
        "jobs_queued": len(job_ids),
        "job_ids": job_ids[:20],
        "errors": errors,
        "last_synced_at": config["confluence_last_synced_at"],
    }
