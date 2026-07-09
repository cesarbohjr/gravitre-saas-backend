"""Recent activity feed for connector writes and other non-run events."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    return "does not exist" in str(error).lower()


def record_activity_event(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    source: str,
    event_type: str,
    title: str,
    body: str = "",
    status: str = "completed",
    entity_type: str | None = None,
    entity_id: str | None = None,
    url: str | None = None,
    integration: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    if not org_id or not user_id:
        return None
    row = {
        "org_id": org_id,
        "user_id": user_id,
        "source": source,
        "event_type": event_type,
        "title": title[:200],
        "body": body[:2000],
        "status": status,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "url": url,
        "integration": integration,
        "metadata": metadata or {},
    }
    try:
        response = client.table("activity_events").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "activity event insert failed org_id=%s user_id=%s source=%s: %s",
            org_id,
            user_id,
            source,
            exc,
        )
        return None
    if response.data and isinstance(response.data, list) and response.data:
        return str(response.data[0].get("id") or "") or None
    return None


def list_recent_activity(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    limit: int = 12,
    source: str | None = None,
) -> list[dict[str, Any]]:
    if not org_id or not user_id:
        return []
    capped = max(1, min(limit, 50))
    query = (
        client.table("activity_events")
        .select(
            "id, source, event_type, title, body, status, entity_type, entity_id, url, integration, metadata, created_at"
        )
        .eq("org_id", org_id)
        .eq("user_id", user_id)
    )
    if source:
        query = query.eq("source", source)
    try:
        response = query.order("created_at", desc=True).limit(capped).execute()
    except Exception as exc:  # noqa: BLE001
        if _is_missing_table_error(exc):
            return []
        logger.warning("activity feed list failed org_id=%s user_id=%s: %s", org_id, user_id, exc)
        return []
    if getattr(response, "error", None) and _is_missing_table_error(response.error):
        return []
    rows = response.data or []
    return [_normalize_activity_row(row) for row in rows if isinstance(row, dict)]


def _normalize_activity_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "source": row.get("source") or "connector_write",
        "event_type": row.get("event_type") or "task_completed",
        "title": row.get("title") or "Activity",
        "body": row.get("body") or "",
        "status": row.get("status") or "completed",
        "entity_type": row.get("entity_type"),
        "entity_id": row.get("entity_id"),
        "url": row.get("url"),
        "integration": row.get("integration"),
        "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        "created_at": row.get("created_at") or datetime.now(timezone.utc).isoformat(),
    }
