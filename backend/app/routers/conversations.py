"""Assistant conversation history API (sidebar metadata + messages)."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.supabase_response import response_error
from app.services.conversation_write_guard import (
    ConversationWriteBlockedError,
    assert_conversation_create_allowed,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
logger = get_logger(__name__)


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
        "archived_at": row.get("archived_at"),
        "pinned_at": row.get("pinned_at"),
    }


def _missing_column_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return "column" in message and "does not exist" in message


def _conversation_sort_key(row: dict) -> tuple:
    """Pinned first, then updated_at DESC (ISO strings sort lexicographically)."""
    pinned = "1" if row.get("pinned_at") else "0"
    return (pinned, str(row.get("updated_at") or row.get("created_at") or ""))


def _merge_conversation_rows(*groups: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for group in groups:
        for row in group:
            conv_id = str(row.get("id") or "")
            if conv_id:
                by_id[conv_id] = row
    return sorted(by_id.values(), key=_conversation_sort_key, reverse=True)


def _conversation_ids_matching_message_content(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    term: str,
    limit: int = 200,
) -> list[str]:
    owned = (
        client.table("conversations")
        .select("id")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .is_("deleted_at", "null")
        .limit(500)
        .execute()
    )
    if response_error(owned) or _is_missing_table_error(response_error(owned)):
        return []
    owned_ids = [str(row.get("id")) for row in (owned.data or []) if row.get("id")]
    if not owned_ids:
        return []
    matched: set[str] = set()
    # PostgREST in_ filters are practical in chunks.
    chunk_size = 100
    for index in range(0, len(owned_ids), chunk_size):
        chunk = owned_ids[index : index + chunk_size]
        response = (
            client.table("conversation_messages")
            .select("conversation_id")
            .in_("conversation_id", chunk)
            .ilike("content", f"%{term}%")
            .limit(limit)
            .execute()
        )
        if response_error(response) or _is_missing_table_error(response_error(response)):
            break
        for row in response.data or []:
            conv_id = row.get("conversation_id")
            if conv_id:
                matched.add(str(conv_id))
        if len(matched) >= limit:
            break
    return list(matched)


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


class BulkDeleteRequest(BaseModel):
    ids: list[str] = Field(default_factory=list, min_length=1)


class ConversationMessageAppend(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    content: str = Field(default="", max_length=200_000)
    tool_calls: list[dict[str, Any]] | None = None


class AppendMessagesRequest(BaseModel):
    messages: list[ConversationMessageAppend] = Field(min_length=1, max_length=20)


def _require_org(org_id: str | None) -> str:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return org_id


def _hard_delete_owned_conversation(
    client: Any,
    *,
    conversation_id: str,
    org_id: str,
    user_id: str,
) -> None:
    response = (
        client.table("conversations")
        .delete()
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .select("id")
        .execute()
    )
    error = response_error(response)
    if error:
        raise HTTPException(status_code=500, detail=str(error))
    if not (response.data or []):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


def _delete_owned_conversation(
    client: Any,
    *,
    conversation_id: str,
    org_id: str,
    user_id: str,
) -> None:
    """Soft-delete a conversation, falling back to hard delete when lifecycle columns are missing."""
    now = _now_iso()
    try:
        response = (
            client.table("conversations")
            .update({"deleted_at": now, "updated_at": now})
            .eq("id", conversation_id)
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .select("id")
            .execute()
        )
        error = response_error(response)
        if error and _missing_column_error(error):
            _hard_delete_owned_conversation(
                client,
                conversation_id=conversation_id,
                org_id=org_id,
                user_id=user_id,
            )
            return
        if error:
            raise HTTPException(status_code=500, detail=str(error))
        if response.data:
            return
        _hard_delete_owned_conversation(
            client,
            conversation_id=conversation_id,
            org_id=org_id,
            user_id=user_id,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        if _missing_column_error(exc):
            _hard_delete_owned_conversation(
                client,
                conversation_id=conversation_id,
                org_id=org_id,
                user_id=user_id,
            )
            return
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _get_owned_conversation(
    client: Any,
    *,
    conversation_id: str,
    org_id: str,
    user_id: str,
    include_deleted: bool = False,
    use_lifecycle_columns: bool = True,
) -> dict:
    select = (
        "id, org_id, user_id, title, preview, message_count, created_at, updated_at, archived_at, deleted_at"
        if use_lifecycle_columns
        else "id, org_id, user_id, title, preview, message_count, created_at, updated_at"
    )
    query = (
        client.table("conversations")
        .select(select)
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .eq("user_id", user_id)
    )
    if use_lifecycle_columns and not include_deleted:
        query = query.is_("deleted_at", "null")
    response = query.limit(1).execute()
    error = response_error(response)
    if error and _missing_column_error(error) and use_lifecycle_columns:
        return _get_owned_conversation(
            client,
            conversation_id=conversation_id,
            org_id=org_id,
            user_id=user_id,
            include_deleted=include_deleted,
            use_lifecycle_columns=False,
        )
    if _is_missing_table_error(error):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if error:
        raise HTTPException(status_code=500, detail=str(error))
    rows = response.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return rows[0]


def _find_duplicate_conversation(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    title: str,
) -> dict | None:
    """Return an existing same-day conversation with a matching title."""
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    response = (
        client.table("conversations")
        .select("id, title, preview, message_count, created_at, updated_at")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .is_("deleted_at", "null")
        .ilike("title", title.strip())
        .gte("created_at", since)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if _is_missing_table_error(response_error(response)):
        return None
    rows = response.data or []
    return rows[0] if rows else None


def _list_conversations_query(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    include_archived: bool,
    select_cols: str,
):
    query = (
        client.table("conversations")
        .select(select_cols)
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .is_("deleted_at", "null")
    )
    if not include_archived:
        query = query.is_("archived_at", "null")
    return query


@router.get("")
async def list_conversations(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    search: str | None = Query(default=None, max_length=200),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    org_id = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    select_cols = "id, title, preview, message_count, created_at, updated_at, archived_at, pinned_at"
    select_fallback = "id, title, preview, message_count, created_at, updated_at, archived_at"
    term = (search or "").strip()

    def _order_rows(query: Any, *, page: bool = True):
        # Pinned first (non-null pinned_at), then recency. Frontend groups; does not re-sort.
        try:
            ordered = query.order("pinned_at", desc=True, nullsfirst=False).order(
                "updated_at", desc=True
            )
        except TypeError:
            ordered = query.order("updated_at", desc=True)
        if page:
            return ordered.range(offset, offset + limit - 1).execute()
        return ordered.limit(min(200, max(limit + offset, limit))).execute()

    if term:
        title_query = _list_conversations_query(
            client,
            org_id=org_id,
            user_id=user["user_id"],
            include_archived=include_archived,
            select_cols=select_cols,
        ).ilike("title", f"%{term}%")
        title_response = _order_rows(title_query, page=False)
        title_error = response_error(title_response)
        if title_error and _missing_column_error(title_error):
            title_query = _list_conversations_query(
                client,
                org_id=org_id,
                user_id=user["user_id"],
                include_archived=include_archived,
                select_cols=select_fallback,
            ).ilike("title", f"%{term}%")
            title_response = title_query.order("updated_at", desc=True).limit(200).execute()
        if _is_missing_table_error(response_error(title_response)):
            return {"conversations": []}
        if response_error(title_response):
            raise HTTPException(status_code=500, detail=str(response_error(title_response)))

        content_ids = _conversation_ids_matching_message_content(
            client,
            org_id=org_id,
            user_id=user["user_id"],
            term=term,
        )
        content_rows: list[dict] = []
        if content_ids:
            content_query = _list_conversations_query(
                client,
                org_id=org_id,
                user_id=user["user_id"],
                include_archived=include_archived,
                select_cols=select_cols,
            ).in_("id", content_ids)
            content_response = _order_rows(content_query, page=False)
            content_error = response_error(content_response)
            if content_error and _missing_column_error(content_error):
                content_query = _list_conversations_query(
                    client,
                    org_id=org_id,
                    user_id=user["user_id"],
                    include_archived=include_archived,
                    select_cols=select_fallback,
                ).in_("id", content_ids)
                content_response = content_query.order("updated_at", desc=True).limit(200).execute()
            if not response_error(content_response):
                content_rows = content_response.data or []

        merged = _merge_conversation_rows(title_response.data or [], content_rows)
        page = merged[offset : offset + limit]
        return {"conversations": [_normalize_conversation(row) for row in page]}

    query = _list_conversations_query(
        client,
        org_id=org_id,
        user_id=user["user_id"],
        include_archived=include_archived,
        select_cols=select_cols,
    )
    response = _order_rows(query, page=True)
    list_error = response_error(response)
    if list_error and _missing_column_error(list_error):
        fallback_query = _list_conversations_query(
            client,
            org_id=org_id,
            user_id=user["user_id"],
            include_archived=include_archived,
            select_cols=select_fallback,
        )
        response = fallback_query.order("updated_at", desc=True).range(
            offset, offset + limit - 1
        ).execute()
        if response_error(response):
            raise HTTPException(status_code=500, detail=str(response_error(response)))
        return {"conversations": [_normalize_conversation(row) for row in (response.data or [])]}
    if _is_missing_table_error(response_error(response)):
        return {"conversations": []}
    if response_error(response):
        raise HTTPException(status_code=500, detail=str(response_error(response)))
    return {"conversations": [_normalize_conversation(row) for row in (response.data or [])]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreateRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id = _require_org(org_id)
    try:
        from app.services.conversation_write_guard import bind_request_actor

        bind_request_actor(
            actor_id=str(user.get("user_id") or ""),
            actor_email=str(user.get("email") or ""),
        )
        assert_conversation_create_allowed(
            org_id,
            actor_id=str(user.get("user_id") or ""),
            actor_email=str(user.get("email") or "") or None,
        )
    except ConversationWriteBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    now = _now_iso()
    title = (body.title or "").strip() or "New conversation"
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    duplicate = _find_duplicate_conversation(
        client,
        org_id=org_id,
        user_id=user["user_id"],
        title=title,
    )
    if duplicate:
        return _normalize_conversation(duplicate)
    row = {
        "org_id": org_id,
        "user_id": user["user_id"],
        "title": title,
        "preview": None,
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    response = client.table("conversations").insert(row).execute()
    if _is_missing_table_error(response_error(response)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversations storage is not available",
        )
    if response_error(response):
        raise HTTPException(status_code=500, detail=str(response_error(response)))
    created = (response.data or [None])[0]
    if not created:
        raise HTTPException(status_code=500, detail="Conversation insert returned no row")
    return _normalize_conversation(created)


@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_conversations(
    body: BulkDeleteRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    org_id = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    seen: set[str] = set()
    for raw_id in body.ids:
        conversation_id = raw_id.strip()
        if not conversation_id or conversation_id in seen:
            continue
        seen.add(conversation_id)
        try:
            _delete_owned_conversation(
                client,
                conversation_id=conversation_id,
                org_id=org_id,
                user_id=user["user_id"],
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                continue
            raise


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
    if response_error(response):
        raise HTTPException(status_code=500, detail=str(response_error(response)))
    updated = (response.data or [None])[0]
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _normalize_conversation(updated)


@router.post("/{conversation_id}/archive")
async def archive_conversation(
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
    now = _now_iso()
    response = (
        client.table("conversations")
        .update({"archived_at": now, "updated_at": now})
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .eq("user_id", user["user_id"])
        .execute()
    )
    if response_error(response):
        raise HTTPException(status_code=500, detail=str(response_error(response)))
    updated = (response.data or [None])[0]
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _normalize_conversation(updated)


@router.post("/{conversation_id}/unarchive")
async def unarchive_conversation(
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
    now = _now_iso()
    response = (
        client.table("conversations")
        .update({"archived_at": None, "updated_at": now})
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .eq("user_id", user["user_id"])
        .execute()
    )
    if response_error(response):
        raise HTTPException(status_code=500, detail=str(response_error(response)))
    updated = (response.data or [None])[0]
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _normalize_conversation(updated)


@router.post("/{conversation_id}/pin")
async def pin_conversation(
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
    now = _now_iso()
    response = (
        client.table("conversations")
        .update({"pinned_at": now, "updated_at": now})
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .eq("user_id", user["user_id"])
        .execute()
    )
    if response_error(response):
        if _missing_column_error(response_error(response)):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Conversation pin storage is not available",
            )
        raise HTTPException(status_code=500, detail=str(response_error(response)))
    updated = (response.data or [None])[0]
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _normalize_conversation(updated)


@router.post("/{conversation_id}/unpin")
async def unpin_conversation(
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
    now = _now_iso()
    response = (
        client.table("conversations")
        .update({"pinned_at": None, "updated_at": now})
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .eq("user_id", user["user_id"])
        .execute()
    )
    if response_error(response):
        if _missing_column_error(response_error(response)):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Conversation pin storage is not available",
            )
        raise HTTPException(status_code=500, detail=str(response_error(response)))
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
    _delete_owned_conversation(
        client,
        conversation_id=conversation_id,
        org_id=org_id,
        user_id=user["user_id"],
    )


@router.get("/{conversation_id}/messages")
async def list_conversation_messages(
    conversation_id: str,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id = _require_org(org_id)
    load_started = time.monotonic()
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
    if _is_missing_table_error(response_error(response)):
        logger.info(
            "chat_perf stage=conversation_load conversation_id=%s ms=%s messages=0",
            conversation_id,
            int((time.monotonic() - load_started) * 1000),
        )
        return {"messages": []}
    if response_error(response):
        raise HTTPException(status_code=500, detail=str(response_error(response)))
    rows = [_normalize_message(row) for row in (response.data or [])]
    logger.info(
        "chat_perf stage=conversation_load conversation_id=%s ms=%s messages=%s",
        conversation_id,
        int((time.monotonic() - load_started) * 1000),
        len(rows),
    )
    return {"messages": rows}


@router.post("/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def append_conversation_messages(
    conversation_id: str,
    body: AppendMessagesRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    owned = _get_owned_conversation(
        client,
        conversation_id=conversation_id,
        org_id=org_id,
        user_id=user["user_id"],
    )
    base_time = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    preview = owned.get("preview")
    for index, message in enumerate(body.messages):
        role = (message.role or "").strip().lower()
        if role not in {"user", "assistant"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message role")
        content = message.content or ""
        if role == "assistant" and content.strip():
            preview = content[:200]
        # Distinct created_at per row so audit timestamps stay ordered within a batch.
        created_at = (base_time + timedelta(milliseconds=index)).isoformat()
        rows.append(
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "tool_calls": message.tool_calls,
                "created_at": created_at,
            }
        )
    response = client.table("conversation_messages").insert(rows).execute()
    if _is_missing_table_error(response_error(response)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversation messages storage is not available",
        )
    if response_error(response):
        raise HTTPException(status_code=500, detail=str(response_error(response)))
    inserted = response.data or []
    current_count = int(owned.get("message_count") or 0)
    now = base_time.isoformat()
    client.table("conversations").update(
        {
            "preview": preview,
            "message_count": current_count + len(inserted),
            "updated_at": now,
        }
    ).eq("id", conversation_id).eq("org_id", org_id).eq("user_id", user["user_id"]).execute()
    return {"messages": [_normalize_message(row) for row in inserted]}
