"""Assistant conversation history API (sidebar metadata + messages)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return (
        "does not exist" in message
        or "relation" in message and "does not exist" in message
        or "undefined_table" in message
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_conversation(row: dict) -> dict:
    return {
        "id": str(row.get("id") or ""),
        "title": row.get("title") or "New conversation",
        "preview": row.get("preview"),
        "created_at": row.get("created_at") or _now_iso(),
        "updated_at": row.get("updated_at") or row.get("created_at") or _now_iso(),
        "message_count": int(row.get("message_count") or 0),
    }


def _normalize_message(row: dict) -> dict:
    return {
        "id": str(row.get("id") or ""),
        "conversation_id": str(row.get("conversation_id") or ""),
        "role": row.get("role") or "user",
        "content": row.get("content") or "",
        "tool_calls": row.get("tool_calls"),
        "created_at": row.get("created_at") or _now_iso(),
    }


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)


class ConversationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)


def _require_org(org_id: str | None) -> str:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return org_id


def _get_owned_conversation(
    client: Any,
    *,
    conversation_id: str,
    org_id: str,
    user_id: str,
) -> dict:
    response = (
        client.table("conversations")
        .select("id, org_id, user_id, title, preview, message_count, created_at, updated_at")
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if _is_missing_table_error(response.error):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    rows = response.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return rows[0]


@router.get("")
async def list_conversations(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("conversations")
        .select("id, title, preview, message_count, created_at, updated_at")
        .eq("org_id", org_id)
        .eq("user_id", user["user_id"])
        .order("updated_at", desc=True)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"conversations": []}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"conversations": [_normalize_conversation(row) for row in (response.data or [])]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreateRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id = _require_org(org_id)
    now = _now_iso()
    title = (body.title or "").strip() or "New conversation"
    row = {
        "org_id": org_id,
        "user_id": user["user_id"],
        "title": title,
        "preview": None,
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = client.table("conversations").insert(row).execute()
    if _is_missing_table_error(response.error):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversations storage is not available",
        )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    created = (response.data or [None])[0]
    if not created:
        raise HTTPException(status_code=500, detail="Conversation insert returned no row")
    return _normalize_conversation(created)


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = _get_owned_conversation(
        client,
        conversation_id=conversation_id,
        org_id=org_id,
        user_id=user["user_id"],
    )
    return _normalize_conversation(row)


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdateRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _get_owned_conversation(
        client,
        conversation_id=conversation_id,
        org_id=org_id,
        user_id=user["user_id"],
    )
    updates: dict[str, Any] = {"updated_at": _now_iso()}
    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title cannot be empty")
        updates["title"] = title
    response = (
        client.table("conversations")
        .update(updates)
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .eq("user_id", user["user_id"])
        .execute()
    )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    updated = (response.data or [None])[0]
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _normalize_conversation(updated)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    org_id = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _get_owned_conversation(
        client,
        conversation_id=conversation_id,
        org_id=org_id,
        user_id=user["user_id"],
    )
    response = (
        client.table("conversations")
        .delete()
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .eq("user_id", user["user_id"])
        .execute()
    )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))


@router.get("/{conversation_id}/messages")
async def list_conversation_messages(
    conversation_id: str,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _get_owned_conversation(
        client,
        conversation_id=conversation_id,
        org_id=org_id,
        user_id=user["user_id"],
    )
    response = (
        client.table("conversation_messages")
        .select("id, conversation_id, role, content, tool_calls, created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"messages": []}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"messages": [_normalize_message(row) for row in (response.data or [])]}
