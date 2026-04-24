"""Phase 15: Sources API (alias to RAG sources)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.core.crypto import decrypt_value, encrypt_value, mask_value
from app.core.errors import error_detail
from app.rag.ingest import get_source
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    connection_string: str = Field(..., alias="connectionString")
    environment_id: str | None = Field(default=None, alias="environmentId")


class SourceUpdateRequest(BaseModel):
    name: str | None = None
    connection_string: str | None = Field(default=None, alias="connectionString")
    status: str | None = None


class SourceSyncRequest(BaseModel):
    full_sync: bool | None = Field(default=None, alias="fullSync")


def _mask_connection(value: str | None) -> str | None:
    return mask_value(value)


@router.get("")
async def list_sources(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    r = (
        client.table("rag_sources")
        .select("id, title, name, type, status, environment, tables_count, last_sync_at, connection_string_encrypted")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .is_("deleted_at", "null")
        .order("updated_at", desc=True)
        .execute()
    )
    items = []
    for row in list(r.data or []):
        conn = None
        if row.get("connection_string_encrypted") and settings.encryption_key:
            try:
                conn = decrypt_value(row["connection_string_encrypted"], settings.encryption_key)
            except Exception:
                conn = None
        items.append(
            {
                "id": str(row["id"]),
                "name": row.get("name") or row.get("title") or "",
                "type": row.get("type"),
                "status": row.get("status") or "connected",
                "environment": row.get("environment") or environment_name,
                "tablesCount": row.get("tables_count") or 0,
                "lastSyncAt": row.get("last_sync_at"),
                "connectionString": _mask_connection(conn),
            }
        )
    return {"sources": items}


@router.get("/{source_id}")
async def get_source_route(
    source_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    source = get_source(client, org_id, str(source_id), environment_name=environment_name)
    if not source or source.get("deleted_at"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    conn = None
    if source.get("connection_string_encrypted") and settings.encryption_key:
        try:
            conn = decrypt_value(source["connection_string_encrypted"], settings.encryption_key)
        except Exception:
            conn = None
    return {
        "source": {
            "id": str(source["id"]),
            "name": source.get("name") or source.get("title") or "",
            "type": source.get("type"),
            "status": source.get("status") or "connected",
            "environment": source.get("environment") or environment_name,
            "tablesCount": source.get("tables_count") or 0,
            "lastSyncAt": source.get("last_sync_at"),
            "connectionString": _mask_connection(conn),
        }
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_source_route(
    body: SourceCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    if not settings.encryption_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("ENCRYPTION_KEY not configured", "INVALID_CONFIG"),
        )
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    encrypted = encrypt_value(body.connection_string, settings.encryption_key)
    row = {
        "org_id": org_id,
        "title": body.name,
        "name": body.name,
        "type": body.type,
        "status": "connected",
        "connection_string_encrypted": encrypted,
        "environment": environment_name,
    }
    r = client.table("rag_sources").insert(row).execute()
    if not r.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Source create failed")
    source_id = str(r.data[0]["id"])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="source.created",
        resource_type="source",
        resource_id=source_id,
        metadata={"environment": environment_name},
    )
    return {"id": source_id}


@router.patch("/{source_id}")
async def update_source_route(
    source_id: UUID,
    body: SourceUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    payload: dict = {}
    if body.name is not None:
        payload["title"] = body.name
        payload["name"] = body.name
    if body.status is not None:
        payload["status"] = body.status
    if body.connection_string is not None:
        if not settings.encryption_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_detail("ENCRYPTION_KEY not configured", "INVALID_CONFIG"),
            )
        payload["connection_string_encrypted"] = encrypt_value(body.connection_string, settings.encryption_key)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    updated = (
        client.table("rag_sources")
        .update(payload)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(source_id))
        .is_("deleted_at", "null")
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="source.updated",
        resource_type="source",
        resource_id=str(source_id),
        metadata={"environment": environment_name, "fields": list(payload.keys())},
    )
    return await get_source_route(source_id, _admin[0], org_id, environment_name, settings)


@router.delete("/{source_id}")
async def delete_source_route(
    source_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    existing = (
        client.table("rag_sources")
        .select("id")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(source_id))
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    client.table("rag_sources").update(
        {"deleted_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", str(source_id)).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="source.deleted",
        resource_type="source",
        resource_id=str(source_id),
        metadata={"environment": environment_name},
    )
    return {"success": True}


@router.post("/{source_id}/sync")
async def sync_source_route(
    source_id: UUID,
    body: SourceSyncRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    source = (
        client.table("rag_sources")
        .select("id, status")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(source_id))
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not source.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    client.table("rag_sources").update({"status": "syncing"}).eq("id", str(source_id)).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="source.sync.manual",
        resource_type="source",
        resource_id=str(source_id),
        metadata={"environment": environment_name, "full_sync": bool(body.full_sync)},
    )
    return {"success": True, "status": "syncing"}
