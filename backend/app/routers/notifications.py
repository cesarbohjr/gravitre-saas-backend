"""Notifications API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    return "does not exist" in str(error).lower()


def _normalize_notification(row: dict) -> dict:
    return {
        "id": str(row.get("id") or ""),
        "type": row.get("type") or "system",
        "title": row.get("title") or "Notification",
        "body": row.get("body") or "",
        "entity_type": row.get("entity_type"),
        "entity_id": row.get("entity_id"),
        "url": row.get("url"),
        "is_read": bool(row.get("is_read") or False),
        "is_archived": bool(row.get("is_archived") or False),
        "created_at": row.get("created_at") or datetime.now(timezone.utc).isoformat(),
    }


@router.get("")
async def list_notifications(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    unread_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    query = (
        client.table("notifications")
        .select("id, type, title, body, entity_type, entity_id, url, is_read, is_archived, created_at")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("is_archived", False)
    )
    if unread_only:
        query = query.eq("is_read", False)
    response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    if _is_missing_table_error(response.error):
        return {"notifications": [], "unread_count": 0}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))

    unread = (
        client.table("notifications")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("is_read", False)
        .eq("is_archived", False)
        .execute()
    )
    unread_count = 0
    if unread.error and not _is_missing_table_error(unread.error):
        raise HTTPException(status_code=500, detail=str(unread.error))
    if not unread.error:
        unread_count = int(unread.count or 0)
    return {
        "notifications": [_normalize_notification(row) for row in (response.data or [])],
        "unread_count": unread_count,
    }


@router.get("/unread-count")
async def get_unread_count(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("notifications")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("is_read", False)
        .eq("is_archived", False)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"count": 0}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"count": int(response.count or 0)}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("notifications")
        .update({"is_read": True})
        .eq("id", notification_id)
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"ok": True}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("notifications")
        .update({"is_read": True})
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("is_read", False)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"ok": True}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"ok": True}


@router.post("/{notification_id}/archive")
async def archive_notification(
    notification_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("notifications")
        .update({"is_archived": True})
        .eq("id", notification_id)
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"ok": True}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"ok": True}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("notifications")
        .delete()
        .eq("id", notification_id)
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"ok": True}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"ok": True}


@router.get("/preferences")
async def get_notification_preferences(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("notification_preferences")
        .select("preferences")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"preferences": {}}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    if not response.data:
        return {"preferences": {}}
    return {"preferences": response.data[0].get("preferences") or {}}


@router.patch("/preferences")
async def update_notification_preferences(
    preferences: Annotated[dict[str, bool], Body(...)],
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    payload = {
        "org_id": org_id,
        "user_id": user_id,
        "preferences": preferences,
    }
    response = (
        client.table("notification_preferences")
        .upsert(payload, on_conflict="org_id,user_id")
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"ok": True}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"ok": True}
