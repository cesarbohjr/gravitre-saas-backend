"""BE-11: Write audit events; no PII or query text in metadata."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from supabase import Client


def write_audit_event(
    client: Client,
    org_id: str,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: UUID | str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert one audit event. metadata must not contain PII or user content."""
    payload: dict[str, Any] = {
        "org_id": org_id,
        "action": action,
        "actor_id": actor_id,
        "resource_type": resource_type,
        "resource_id": str(resource_id),
    }
    if metadata is not None:
        payload["metadata"] = metadata
    client.table("audit_events").insert(payload).execute()
    label = action.replace(".", " ").replace("_", " ").title()
    audit_log = {
        "org_id": org_id,
        "action": action,
        "action_label": label,
        "actor": actor_id,
        "resource": str(resource_id),
        "resource_type": resource_type,
        "details": metadata or {},
    }
    if isinstance(metadata, dict) and metadata.get("severity"):
        audit_log["severity"] = metadata.get("severity")
    client.table("audit_logs").insert(audit_log).execute()
