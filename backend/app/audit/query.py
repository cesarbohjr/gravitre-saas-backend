"""BE-12: Read-only audit event query. Cursor-based pagination; org-scoped."""
from __future__ import annotations

import base64
import json
from typing import Any

from supabase import create_client

from app.config import Settings


def _encode_cursor(created_at: str, id_: str) -> str:
    payload = json.dumps({"created_at": created_at, "id": id_}).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, str] | None:
    try:
        padded = cursor + "=" * (4 - len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded)
        data = json.loads(raw.decode("utf-8"))
        c_at = data.get("created_at")
        c_id = data.get("id")
        if isinstance(c_at, str) and isinstance(c_id, str):
            return (c_at, c_id)
    except (ValueError, TypeError, KeyError):
        pass
    return None


def query_audit_events(
    settings: Settings,
    org_id: str,
    resource_type: str,
    resource_id: str,
    limit: int,
    cursor: str | None = None,
    action_prefix: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Return (items, next_cursor). Items are dicts with id, action, actor_id,
    resource_type, resource_id, metadata, created_at. next_cursor is None if
    no more pages.
    """
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    cursor_created_at: str | None = None
    cursor_id: str | None = None
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            cursor_created_at, cursor_id = decoded
    # Request limit+1 to detect next page
    payload: dict[str, Any] = {
        "p_org_id": org_id,
        "p_resource_type": resource_type,
        "p_resource_id": resource_id,
        "p_limit": limit + 1,
        "p_cursor_created_at": cursor_created_at,
        "p_cursor_id": cursor_id,
        "p_action_prefix": action_prefix,
    }
    r = client.rpc("audit_query", payload).execute()
    rows = list(r.data) if r.data else []
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = _encode_cursor(
            last["created_at"] if isinstance(last.get("created_at"), str) else str(last.get("created_at", "")),
            str(last["id"]),
        )
    return (items, next_cursor)


def query_audit_log(
    settings: Settings,
    org_id: str,
    limit: int,
    cursor: str | None = None,
    action: str | None = None,
    action_prefix: str | None = None,
    actor_id: str | None = None,
    resource_type: str | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """List audit events for an org with optional filters."""
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    cursor_created_at: str | None = None
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            cursor_created_at, _ = decoded
    q = (
        client.table("audit_events")
        .select("id, action, actor_id, resource_type, resource_id, metadata, created_at")
        .eq("org_id", org_id)
    )
    if action:
        q = q.eq("action", action)
    elif action_prefix:
        q = q.like("action", f"{action_prefix}%")
    if actor_id:
        q = q.eq("actor_id", actor_id)
    if resource_type:
        q = q.eq("resource_type", resource_type)
    if start_at:
        q = q.gte("created_at", start_at)
    if end_at:
        q = q.lte("created_at", end_at)
    if cursor_created_at:
        q = q.lt("created_at", cursor_created_at)
    r = q.order("created_at", desc=True).order("id", desc=True).limit(limit + 1).execute()
    rows = list(r.data) if r.data else []
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = _encode_cursor(
            last["created_at"] if isinstance(last.get("created_at"), str) else str(last.get("created_at", "")),
            str(last["id"]),
        )
    return (items, next_cursor)
