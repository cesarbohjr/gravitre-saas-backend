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
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

_MONITOR_STATUSES = ("healthy", "active", "syncing", "error", "pending_auth", "connected")
_BATCH_LIMIT = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connector_vendor(row: dict[str, Any]) -> str:
    vendor = row.get("vendor") or row.get("type") or ""
    return str(vendor)


_ROLE_RANK = {"owner": 0, "admin": 1}


def _org_responsible_user(client: Client, org_id: str) -> str | None:
    """Highest-authority member of the org, preferring owner then admin."""
    try:
        rows = (
            client.table("organization_members")
            .select("user_id, role")
            .eq("org_id", org_id)
            .limit(50)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("connector_health_actor_lookup_failed org_id=%s: %s", org_id, exc)
        return None
    candidates = [r for r in rows if r.get("user_id")]
    if not candidates:
        return None
    candidates.sort(key=lambda r: _ROLE_RANK.get(str(r.get("role") or "").lower(), 2))
    return str(candidates[0]["user_id"])


def resolve_connector_audit_actor(
    client: Client,
    org_id: str,
    row: dict[str, Any],
    *,
    cache: dict[str, str | None] | None = None,
) -> str | None:
    """A real, named actor for a background health event.

    These two events previously passed actor_id=None, which write_audit_event
    silently drops (the column is NOT NULL with an FK), so a connector going
    into auth failure left no audit trail at all. The sweep has no request user,
    but the event does have a real owner:

      1. connectors.created_by — the person who connected it. Most specific, and
         the person whose reconnect is needed. Populated for 6 of 19
         status-changeable connectors in production.
      2. the org's owner, then admin — covers the remaining 13, and is the right
         escalation target for a connector nobody is recorded as having created.

    Returns None only when an org has no members at all, and the caller logs
    that loudly rather than writing an event that would be silently discarded.
    """
    created_by = str(row.get("created_by") or "").strip()
    if created_by:
        return created_by
    if cache is not None and org_id in cache:
        return cache[org_id]
    resolved = _org_responsible_user(client, org_id)
    if cache is not None:
        cache[org_id] = resolved
    return resolved


def list_monitored_connectors(client: Client) -> list[dict[str, Any]]:
    """Non-deleted connectors eligible for OAuth health polling."""
    response = (
        client.table("connectors")
        .select("id, org_id, vendor, type, status, environment, config, created_by")
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


def _persist_health_result(
    client: Client,
    row: dict[str, Any],
    result: dict[str, Any],
    *,
    actor_cache: dict[str, str | None] | None = None,
) -> None:
    if result.get("skipped"):
        return

    connector_id = result["connector_id"]
    org_id = result["org_id"]
    config = safe_normalize_stored_dict(row, key="config")
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
    is_failure = new_status == "error"
    is_recovery = new_status in {"healthy", "active"} and result.get("previous_status") in {
        "error",
        "pending_auth",
    }
    if not (is_failure or is_recovery):
        return

    actor_id = resolve_connector_audit_actor(client, org_id, row, cache=actor_cache)
    if not actor_id:
        # Loud rather than silent: write_audit_event would drop this row without
        # an actor, which is how these two events went unrecorded in the first place.
        logger.warning(
            "connector_health_audit_no_actor org_id=%s connector_id=%s status=%s",
            org_id,
            connector_id,
            new_status,
        )
        return

    if is_failure:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id,
            action="connector.auth.failed",
            resource_type="connector",
            resource_id=connector_id,
            metadata={
                "vendor": result.get("vendor"),
                "environment": result.get("environment"),
                "authStatus": result.get("auth_status"),
                "previousStatus": result.get("previous_status"),
                "actorSource": "connector_created_by"
                if row.get("created_by")
                else "org_owner_or_admin",
            },
        )
    else:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id,
            action="connector.connected",
            resource_type="connector",
            resource_id=connector_id,
            metadata={
                "vendor": result.get("vendor"),
                "environment": result.get("environment"),
                "authStatus": result.get("auth_status"),
                "actorSource": "connector_created_by"
                if row.get("created_by")
                else "org_owner_or_admin",
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
    actor_cache: dict[str, str | None] = {}

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
            _persist_health_result(client, row, result, actor_cache=actor_cache)
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
