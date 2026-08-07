"""Data source sync orchestration, history, and SaaS connector linking."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import Client

from app.config import Settings
from app.core.crypto import decrypt_value
from app.core.logging import get_logger
from app.data.connection_service import ConnectionTestError, config_from_encrypted_blob, discover_schema, run_connection_test
from app.data.source_registry import DATA_SOURCE_TYPES, get_source_type
from app.workflows.audit import write_audit_event
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

DEFAULT_SYNC_INTERVAL_SECONDS = 300

SAAS_CONNECTOR_VENDOR_MAP: dict[str, str] = {
    "salesforce": "salesforce",
    "hubspot": "hubspot",
    "stripe": "stripe",
    "notion": "notion",
    "google_sheets": "google_sheets",
    "zendesk": "zendesk",
    "jira": "jira",
    "github": "github",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_source_config(settings: Settings, row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    metadata = row.get("metadata") or {}
    type_id = str(
        (metadata.get("typeId") if isinstance(metadata, dict) else None) or row.get("type") or "postgresql"
    ).lower()
    if not settings.encryption_key or not row.get("connection_string_encrypted"):
        return type_id, {}
    raw = decrypt_value(row["connection_string_encrypted"], settings.encryption_key)
    return type_id, config_from_encrypted_blob(raw)


def list_connectors_for_vendor(
    client: Client,
    org_id: str,
    *,
    environment: str,
    oauth_vendor: str,
) -> list[dict[str, Any]]:
    expected = SAAS_CONNECTOR_VENDOR_MAP.get(oauth_vendor, oauth_vendor)
    response = (
        client.table("connectors")
        .select("id, type, status, config, environment, created_at, updated_at")
        .eq("org_id", org_id)
        .eq("environment", environment)
        .in_("status", ["active", "connected"])
        .execute()
    )
    items: list[dict[str, Any]] = []
    for row in response.data or []:
        connector_type = str(row.get("type") or "").lower()
        config = row.get("config") or {}
        vendor = str(config.get("vendor") or connector_type).lower() if isinstance(config, dict) else connector_type
        if connector_type != expected and vendor != expected:
            continue
        name = config.get("name") if isinstance(config, dict) else None
        items.append(
            {
                "id": str(row["id"]),
                "type": connector_type,
                "status": row.get("status"),
                "name": name or f"{expected} connector",
                "environment": row.get("environment") or environment,
            }
        )
    return items


def list_source_sync_history(
    client: Client,
    org_id: str,
    source_id: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    response = (
        client.table("audit_events")
        .select("id, action, metadata, created_at, actor_id")
        .eq("org_id", org_id)
        .eq("resource_type", "source")
        .eq("resource_id", source_id)
        .like("action", "source.sync%")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    history: list[dict[str, Any]] = []
    for row in response.data or []:
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        status = str(metadata.get("status") or ("success" if "error" not in metadata else "error"))
        history.append(
            {
                "id": str(row["id"]),
                "action": row.get("action"),
                "status": status,
                "records": metadata.get("records", 0),
                "tables": metadata.get("tables", 0),
                "durationMs": metadata.get("durationMs", metadata.get("duration_ms")),
                "error": metadata.get("error"),
                "trigger": metadata.get("trigger", "manual"),
                "createdAt": row.get("created_at"),
            }
        )
    return history


async def sync_source_row(
    client: Client,
    settings: Settings,
    *,
    org_id: str,
    row: dict[str, Any],
    environment: str,
    actor_id: str,
    trigger: str = "manual",
    full_sync: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    source_id = str(row["id"])
    metadata = safe_normalize_stored_dict(row, key='metadata') if isinstance(row.get("metadata"), dict) else {}
    type_id, config = load_source_config(settings, row)
    tables_count = int(metadata.get("tablesCount") or row.get("tables_count") or 0)
    record_count = int(metadata.get("recordCount") or 0)
    status = "connected"
    error_message: str | None = None

    client.table("rag_sources").update({"status": "syncing"}).eq("id", source_id).execute()
    try:
        test_result = await run_connection_test(
            type_id,
            config,
            client=client,
            org_id=org_id,
            environment=environment,
        )
        schema = await discover_schema(type_id, config)
        tables_count = int(test_result.get("tables") or schema.get("tableCount") or 0)
        record_count = int(test_result.get("records") or 0)
        metadata.update(
            {
                "typeId": type_id,
                "tablesCount": tables_count,
                "recordCount": record_count,
                "lastSyncTrigger": trigger,
                "schemaTableCount": schema.get("tableCount", 0),
            }
        )
        if full_sync:
            metadata["lastFullSyncAt"] = _now_iso()
    except ConnectionTestError as exc:
        status = "error"
        error_message = str(exc)
        metadata["lastSyncError"] = error_message

    duration_ms = int((time.perf_counter() - started) * 1000)
    client.table("rag_sources").update(
        {
            "status": status,
            "tables_count": tables_count,
            "last_sync_at": _now_iso(),
            "metadata": metadata,
        }
    ).eq("id", source_id).execute()

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action="source.sync.scheduled" if trigger == "scheduled" else "source.sync.manual",
        resource_type="source",
        resource_id=source_id,
        metadata={
            "environment": environment,
            "trigger": trigger,
            "full_sync": full_sync,
            "tables": tables_count,
            "records": record_count,
            "durationMs": duration_ms,
            "status": "success" if status == "connected" else "error",
            "error": error_message,
        },
    )
    return {
        "success": status == "connected",
        "status": status,
        "tables": tables_count,
        "records": record_count,
        "durationMs": duration_ms,
        "error": error_message,
    }


def _sync_interval_seconds(metadata: dict[str, Any]) -> int:
    raw = metadata.get("syncIntervalSeconds") or metadata.get("sync_interval_seconds")
    try:
        value = int(raw)
        return max(60, value)
    except (TypeError, ValueError):
        return DEFAULT_SYNC_INTERVAL_SECONDS


def _is_due(row: dict[str, Any], *, now: datetime) -> bool:
    metadata = row.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("syncEnabled") is False:
        return False
    last_sync_raw = row.get("last_sync_at")
    interval = _sync_interval_seconds(metadata if isinstance(metadata, dict) else {})
    if not last_sync_raw:
        return True
    try:
        last_sync = datetime.fromisoformat(str(last_sync_raw).replace("Z", "+00:00"))
    except ValueError:
        return True
    return last_sync <= now - timedelta(seconds=interval)


async def run_scheduled_source_syncs(settings: Settings) -> dict[str, Any]:
    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    now = datetime.now(timezone.utc)
    response = (
        client.table("rag_sources")
        .select("id, org_id, environment, status, metadata, type, connection_string_encrypted, tables_count, last_sync_at")
        .is_("deleted_at", "null")
        .in_("status", ["connected", "error", "syncing"])
        .execute()
    )
    due_rows = [row for row in (response.data or []) if _is_due(row, now=now)]
    processed = 0
    errors = 0

    for row in due_rows:
        try:
            result = await sync_source_row(
                client,
                settings,
                org_id=str(row["org_id"]),
                row=row,
                environment=str(row.get("environment") or "production"),
                actor_id="system",
                trigger="scheduled",
            )
            processed += 1
            if not result.get("success"):
                errors += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.warning("scheduled_source_sync_failed source_id=%s error=%s", row.get("id"), exc)

    return {"due_count": len(due_rows), "processed": processed, "errors": errors}


def validate_saas_connector_link(
    client: Client,
    org_id: str,
    *,
    type_id: str,
    config: dict[str, Any],
    environment: str,
) -> list[str]:
    spec = get_source_type(type_id)
    if not spec or spec.get("driver") != "connector":
        return []
    oauth_vendor = spec.get("oauth_vendor") or type_id
    connector_id = str(config.get("connector_id") or "").strip()
    if not connector_id:
        return ["Linked connector is required for this SaaS data source"]
    expected = SAAS_CONNECTOR_VENDOR_MAP.get(str(oauth_vendor), str(oauth_vendor))
    row = (
        client.table("connectors")
        .select("id, type, status, environment, config")
        .eq("org_id", org_id)
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        return ["Connector not found"]
    connector = row.data[0]
    if str(connector.get("environment") or environment) != environment:
        return ["Connector environment does not match current environment"]
    connector_type = str(connector.get("type") or "").lower()
    cfg = connector.get("config") or {}
    vendor = str(cfg.get("vendor") or connector_type).lower() if isinstance(cfg, dict) else connector_type
    if connector_type != expected and vendor != expected:
        return [f"Connector must be a {expected} integration"]
    if str(connector.get("status") or "").lower() not in {"active", "connected"}:
        return ["Connector must be connected before linking"]
    return []
