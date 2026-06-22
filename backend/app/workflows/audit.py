"""BE-11: Write audit events; no PII or query text in metadata."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any
from uuid import UUID

from supabase import Client

from app.services.compliance_service import redact_metadata
from app.services.siem_export_service import build_siem_event, dispatch_siem_event

logger = logging.getLogger(__name__)

_PII_MODE_CACHE: dict[str, tuple[str, float]] = {}
_PII_MODE_TTL_SECONDS = 300


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _get_org_pii_mode(client: Client, org_id: str) -> str:
    now = time.time()
    cached = _PII_MODE_CACHE.get(org_id)
    if cached and cached[1] > now:
        return cached[0]
    mode = "standard"
    try:
        row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
        if row.data:
            settings = row.data[0].get("settings") or {}
            if isinstance(settings, dict):
                enterprise = settings.get("enterprise")
                if isinstance(enterprise, dict):
                    compliance = enterprise.get("compliance")
                    if isinstance(compliance, dict):
                        configured = str(compliance.get("piiMode") or compliance.get("pii_mode") or "").strip().lower()
                        if configured in {"strict", "standard"}:
                            mode = configured
    except Exception as exc:  # noqa: BLE001
        logger.debug("audit_pii_mode_lookup_failed org_id=%s error=%s", org_id, exc)
    _PII_MODE_CACHE[org_id] = (mode, now + _PII_MODE_TTL_SECONDS)
    return mode


def _dispatch_siem_event(client: Client, org_id: str, action: str, resource_type: str, resource_id: str, metadata: dict[str, Any]) -> None:
    try:
        from app.config import get_settings
        from app.services.enterprise_secrets_service import resolve_siem_secret

        settings = get_settings()
        row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
        if not row.data:
            return
        org_settings = row.data[0].get("settings") or {}
        if not isinstance(org_settings, dict):
            return
        enterprise = org_settings.get("enterprise")
        if not isinstance(enterprise, dict):
            return
        siem = enterprise.get("siem")
        if not isinstance(siem, dict) or not siem.get("enabled"):
            return
        endpoint = str(siem.get("endpoint") or "").strip()
        secret = resolve_siem_secret(siem, settings)
        if not endpoint or not secret:
            return
        event = build_siem_event(
            org_id=org_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
        )
        dispatch_siem_event(endpoint=endpoint, secret=secret, event=event)
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_siem_dispatch_failed org_id=%s action=%s error=%s", org_id, action, exc)


def _schedule_siem_dispatch(
    client: Client,
    org_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, Any],
) -> None:
    thread = threading.Thread(
        target=_dispatch_siem_event,
        args=(client, org_id, action, resource_type, resource_id, metadata),
        daemon=True,
    )
    thread.start()


def write_audit_event(
    client: Client,
    org_id: str,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: UUID | str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert audit rows. Never raises — audit must not break product flows."""
    resource_id_str = str(resource_id)
    pii_mode = _get_org_pii_mode(client, org_id)
    meta = redact_metadata(metadata or {}, mode=pii_mode)

    events_row: dict[str, Any] = {
        "org_id": org_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id_str,
        "metadata": meta,
    }
    if _is_uuid(actor_id):
        events_row["actor_id"] = actor_id

    events_ok = False
    logs_ok = False
    try:
        client.table("audit_events").insert(events_row).execute()
        events_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_events insert failed action=%s: %s", action, exc)

    label = action.replace(".", " ").replace("_", " ").title()
    contract_row: dict[str, Any] = {
        "org_id": org_id,
        "action": action,
        "resource_type": resource_type,
        "details": meta,
    }
    if _is_uuid(actor_id):
        contract_row["actor_id"] = actor_id
    if _is_uuid(resource_id_str):
        contract_row["resource_id"] = resource_id_str

    legacy_row: dict[str, Any] = {
        "org_id": org_id,
        "action": action,
        "action_label": label,
        "actor": actor_id,
        "resource": resource_id_str,
        "resource_type": resource_type,
        "details": meta,
    }

    for row in (contract_row, legacy_row):
        try:
            client.table("audit_logs").insert(row).execute()
            logs_ok = True
            break
        except Exception as exc:  # noqa: BLE001
            logger.debug("audit_logs insert attempt failed action=%s: %s", action, exc)

    if events_ok and not logs_ok:
        logger.warning(
            "audit_dual_write_gap org_id=%s action=%s events=ok logs=failed",
            org_id,
            action,
        )
    elif logs_ok and not events_ok:
        logger.warning(
            "audit_dual_write_gap org_id=%s action=%s events=failed logs=ok",
            org_id,
            action,
        )

    if events_ok or logs_ok:
        _schedule_siem_dispatch(client, org_id, action, resource_type, resource_id_str, meta)
