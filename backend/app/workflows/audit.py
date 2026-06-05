"""BE-11: Write audit events; no PII or query text in metadata."""
from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

from supabase import Client

logger = logging.getLogger(__name__)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


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
    meta = metadata or {}

    events_row: dict[str, Any] = {
        "org_id": org_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id_str,
        "metadata": meta,
    }
    if _is_uuid(actor_id):
        events_row["actor_id"] = actor_id

    try:
        client.table("audit_events").insert(events_row).execute()
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
            break
        except Exception as exc:  # noqa: BLE001
            logger.debug("audit_logs insert attempt failed action=%s: %s", action, exc)
