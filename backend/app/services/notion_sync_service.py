"""Notion workspace → department-scoped RAG sync (STA-43)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.connectors.notion import (
    NotionAPIError,
    collect_database_page_ids,
    export_page_text,
    normalize_search_result,
    search,
)
from app.connectors.notion_oauth import ensure_notion_session
from app.rag.ingest import create_ingest_job, create_source, get_source
from app.core.safe_dict import safe_normalize_stored_dict

logger = logging.getLogger(__name__)

STALE_SYNC_HOURS = 24


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_notion_sync_targets(connector: dict[str, Any]) -> list[dict[str, Any]]:
    config = connector.get("config") or {}
    targets = config.get("notion_sync_targets")
    return list(targets) if isinstance(targets, list) else []


def get_notion_sync_status(connector: dict[str, Any]) -> dict[str, Any]:
    config = connector.get("config") or {}
    last_synced = config.get("notion_last_synced_at")
    stale = False
    if last_synced:
        try:
            ts = datetime.fromisoformat(str(last_synced).replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            stale = age_hours >= STALE_SYNC_HOURS
        except ValueError:
            stale = True
    elif get_notion_sync_targets(connector):
        stale = True
    return {
        "targets": get_notion_sync_targets(connector),
        "rag_source_id": config.get("notion_rag_source_id"),
        "department_id": config.get("notion_department_id"),
        "workspace_id": config.get("notion_workspace_id"),
        "workspace_name": config.get("notion_workspace_name"),
        "last_synced_at": last_synced,
        "stale": stale,
        "stale_threshold_hours": STALE_SYNC_HOURS,
    }


def set_notion_sync_config(
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
    config = safe_normalize_stored_dict(connector, key="config")
    if targets is not None:
        normalized: list[dict[str, Any]] = []
        for item in targets:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            normalized.append(
                {
                    "id": str(item["id"]),
                    "type": str(item.get("type") or "page"),
                    "title": str(item.get("title") or item["id"]),
                }
            )
        config["notion_sync_targets"] = normalized
    if department_id is not None:
        if department_id:
            config["notion_department_id"] = str(department_id)
        else:
            config.pop("notion_department_id", None)
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return get_notion_sync_status({**connector, "config": config})


def ensure_notion_rag_source(
    client: Any,
    org_id: str,
    connector: dict[str, Any],
    settings: Settings,
    *,
    created_by: str,
) -> str:
    config = safe_normalize_stored_dict(connector, key="config")
    existing = config.get("notion_rag_source_id")
    environment = str(connector.get("environment") or "production")
    department_id = config.get("notion_department_id")
    if existing and get_source(client, org_id, str(existing), environment_name=environment):
        return str(existing)

    workspace = config.get("notion_workspace_name") or connector.get("name") or "Notion"
    source = create_source(
        client,
        org_id,
        title=f"Notion — {workspace}",
        type_="notion",
        metadata={"connector_id": connector.get("id"), "workspace_id": config.get("notion_workspace_id")},
        created_by=created_by,
        environment_name=environment,
        department_id=str(department_id) if department_id else None,
    )
    source_id = str(source["id"])
    config["notion_rag_source_id"] = source_id
    client.table("connectors").update({"config": config}).eq("id", connector["id"]).eq("org_id", org_id).execute()
    return source_id


def search_notion(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    query: str | None = None,
    filter_object: str | None = None,
) -> list[dict[str, Any]]:
    token, err = ensure_notion_session(client, org_id, connector_id, settings)
    if err or not token:
        raise ValueError(err or "Notion not connected")
    data = search(token, query=query, filter_object=filter_object)
    results: list[dict[str, Any]] = []
    for item in data.get("results") or []:
        if isinstance(item, dict):
            results.append(normalize_search_result(item))
    return results


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
    last_edited_time: str | None,
) -> str:
    body = text.strip()
    if not body:
        body = f"(empty Notion page {page_id})"
    job = create_ingest_job(
        client,
        org_id,
        source_id,
        external_id=f"notion:page:{page_id}",
        created_by=created_by,
        request_payload={
            "title": title,
            "external_id": f"notion:page:{page_id}",
            "text": body,
            "metadata": {
                "notion_page_id": page_id,
                "notion_last_edited_time": last_edited_time,
            },
        },
        environment_name=environment_name,
    )
    return str(job["id"])


def run_notion_sync(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    actor_id: str,
    full_sync: bool = False,
) -> dict[str, Any]:
    """Sync configured Notion pages/databases into RAG ingest jobs."""
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
    targets = get_notion_sync_targets(connector)
    if not targets:
        raise ValueError("No Notion sync targets configured")

    token, err = ensure_notion_session(client, org_id, connector_id, settings)
    if err or not token:
        raise ValueError(err or "Notion not connected")

    source_id = ensure_notion_rag_source(client, org_id, connector, settings, created_by=actor_id)
    environment = str(connector.get("environment") or "production")

    job_ids: list[str] = []
    pages_synced = 0
    errors: list[str] = []

    for target in targets:
        target_id = str(target.get("id") or "")
        target_type = str(target.get("type") or "page")
        page_ids: list[str] = []
        if target_type == "database":
            try:
                page_ids = collect_database_page_ids(token, target_id)
            except NotionAPIError as exc:
                errors.append(f"database {target_id}: {exc}")
                continue
        else:
            page_ids = [target_id]

        for page_id in page_ids:
            try:
                title, body, edited = export_page_text(token, page_id)
                job_id = _queue_page_ingest(
                    client,
                    org_id=org_id,
                    source_id=source_id,
                    page_id=page_id,
                    title=title or target.get("title") or page_id,
                    text=body,
                    created_by=actor_id,
                    environment_name=environment,
                    last_edited_time=edited,
                )
                job_ids.append(job_id)
                pages_synced += 1
            except NotionAPIError as exc:
                errors.append(f"page {page_id}: {exc}")

    config = safe_normalize_stored_dict(connector, key="config")
    config["notion_last_synced_at"] = _now_iso()
    config["notion_rag_source_id"] = source_id
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()

    logger.info(
        "notion_sync_completed org_id=%s connector_id=%s pages=%s jobs=%s errors=%s",
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
        "last_synced_at": config["notion_last_synced_at"],
    }
