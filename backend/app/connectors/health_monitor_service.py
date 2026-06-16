"""Background connector OAuth health checks (token validity + status sync)."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client

from app.config import Settings
from app.connectors.connection_health import map_auth_status_to_connector_status, resolve_connector_auth_status
from app.core.logging import get_logger
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)

_MONITOR_STATUSES = ("healthy", "active", "syncing", "error", "pending_auth", "connected")
_BATCH_LIMIT = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connector_vendor(row: dict[str, Any]) -> str:
    vendor = row.get("vendor") or row.get("type") or ""
    return str(vendor)


def list_monitored_connectors(client: Client) -> list[dict[str, Any]]:
    """Non-deleted connectors eligible for OAuth health polling."""
    response = (
        client.table("connectors")
        .select("id, org_id, vendor, type, status, environment, config")
        .is_("deleted_at", "null")
        .in_("status", list(_MONITOR_STATUSES))
        .order("updated_at", desc=True)
        .limit(_BATCH_LIMIT)
        .execute()
    )
    return [dict(row) for row in (response.data or [])]


def check_connector_health(
    client: Client,
    row: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    """Resolve OAuth auth status and derive connector status."""
    org_id = str(row["org_id"])
    connector_id = str(row["id"])
    vendor = _connector_vendor(row)
    environment_name = str(row.get("environment") or "production")
    current_status = str(row.get("status") or "healthy")

    started = time.perf_counter()
    auth_status = resolve_connector_auth_status(
        client,
        org_id,
        connector_id,
        vendor,
        settings,
        environment_name=environment_name,
    )
    latency_ms = max(int((time.perf_counter() - started) * 1000), 0)

    if auth_status is None:
        return {"skipped": True, "latency_ms": latency_ms}

    new_status = map_auth_status_to_connector_status(auth_status, current_status)
    return {
        "skipped": False,
        "org_id": org_id,
        "connector_id": connector_id,
        "vendor": vendor,
        "environment": environment_name,
        "auth_status": auth_status,
        "status": new_status,
        "previous_status": current_status,
        "latency_ms": latency_ms,
        "changed": new_status != current_status,
        "name": row.get("name") or vendor or connector_id,
    }


def _persist_health_result(client: Client, row: dict[str, Any], result: dict[str, Any]) -> None:
    if result.get("skipped"):
        return

    connector_id = result["connector_id"]
    org_id = result["org_id"]
    config = dict(row.get("config") or {})
    config["health"] = {
        "checkedAt": _now_iso(),
        "latencyMs": result["latency_ms"],
        "authStatus": result["auth_status"],
    }
    payload: dict[str, Any] = {"config": config, "updated_at": _now_iso()}
    if result.get("changed"):
        payload["status"] = result["status"]

    client.table("connectors").update(payload).eq("id", connector_id).eq("org_id", org_id).execute()

    if not result.get("changed"):
        return

    new_status = str(result["status"])
    if new_status == "error":
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=None,
            action="connector.auth.failed",
            resource_type="connector",
            resource_id=connector_id,
            metadata={
                "vendor": result.get("vendor"),
                "environment": result.get("environment"),
                "authStatus": result.get("auth_status"),
                "previousStatus": result.get("previous_status"),
            },
        )
    elif new_status in {"healthy", "active"} and result.get("previous_status") in {"error", "pending_auth"}:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=None,
            action="connector.connected",
            resource_type="connector",
            resource_id=connector_id,
            metadata={
                "vendor": result.get("vendor"),
                "environment": result.get("environment"),
                "authStatus": result.get("auth_status"),
            },
        )


def run_connector_health_monitor(settings: Settings) -> dict[str, Any]:
    """Poll OAuth connector health for all orgs (service role)."""
    if settings.disable_connectors:
        return {"disabled": True, "checked": 0, "updated": 0, "errors": 0, "skipped": 0}

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows = list_monitored_connectors(client)

    checked = 0
    updated = 0
    skipped = 0
    errors = 0
    total_latency_ms = 0

    for row in rows:
        try:
            result = check_connector_health(client, row, settings)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.warning(
                "connector_health_check_failed org_id=%s connector_id=%s: %s",
                row.get("org_id"),
                row.get("id"),
                exc,
            )
            continue

        if result.get("skipped"):
            skipped += 1
            continue

        checked += 1
        total_latency_ms += int(result.get("latency_ms") or 0)
        try:
            _persist_health_result(client, row, result)
            if result.get("changed"):
                updated += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.warning(
                "connector_health_persist_failed org_id=%s connector_id=%s: %s",
                row.get("org_id"),
                row.get("id"),
                exc,
            )

    summary = {
        "disabled": False,
        "candidates": len(rows),
        "checked": checked,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "avg_latency_ms": round(total_latency_ms / checked, 1) if checked else 0,
    }
    logger.info(
        "connector_health_tick candidates=%s checked=%s updated=%s errors=%s avg_latency_ms=%s",
        summary["candidates"],
        summary["checked"],
        summary["updated"],
        summary["errors"],
        summary["avg_latency_ms"],
    )
    return summary
