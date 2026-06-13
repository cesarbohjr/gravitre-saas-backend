"""Phase 15+: Sources API — registry-backed connections and AI query layer."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.core.crypto import decrypt_value, encrypt_value, mask_value
from app.core.errors import error_detail
from app.data.connection_service import ConnectionTestError, config_from_encrypted_blob, discover_schema, run_connection_test
from app.data.query_layer import natural_language_query, suggest_exploration_questions
from app.data.source_registry import (
    CATEGORY_LABELS,
    list_source_types,
    serialize_connection_config,
    validate_connection_config,
)
from app.rag.ingest import get_source
from app.services.source_sync_service import (
    DEFAULT_SYNC_INTERVAL_SECONDS,
    list_connectors_for_vendor,
    list_source_sync_history,
    sync_source_row,
    validate_saas_connector_link,
)
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    type_id: str | None = Field(default=None, alias="typeId")
    description: str | None = None
    connection_string: str | None = Field(default=None, alias="connectionString")
    config: dict[str, Any] | None = None
    environment_id: str | None = Field(default=None, alias="environmentId")


class SourceUpdateRequest(BaseModel):
    name: str | None = None
    connection_string: str | None = Field(default=None, alias="connectionString")
    config: dict[str, Any] | None = None
    status: str | None = None


class SourceSyncRequest(BaseModel):
    full_sync: bool | None = Field(default=None, alias="fullSync")


class SourceTestRequest(BaseModel):
    type_id: str = Field(..., alias="typeId")
    config: dict[str, Any] | None = None
    connection_string: str | None = Field(default=None, alias="connectionString")


class SourceQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)


def _mask_connection(value: str | None) -> str | None:
    return mask_value(value)


def _resolve_type_id(body_type: str, type_id: str | None) -> str:
    if type_id:
        return type_id.strip().lower()
    normalized = body_type.strip().lower().replace(" ", "_")
    aliases = {
        "postgresql": "postgresql",
        "postgres": "postgresql",
        "mysql": "mysql",
        "mongodb": "mongodb",
        "snowflake": "snowflake",
        "bigquery": "bigquery",
        "google_bigquery": "bigquery",
        "microsoft_sql_server": "mssql",
        "sql_server": "mssql",
        "supabase": "supabase_db",
    }
    return aliases.get(normalized, normalized)


def _build_config_payload(body: SourceCreateRequest | SourceUpdateRequest, type_id: str) -> dict[str, Any]:
    raw_config = dict(body.config or {})
    if getattr(body, "connection_string", None):
        raw_config.setdefault("connection_string", body.connection_string)
    return serialize_connection_config(type_id, raw_config)


def _serialize_source_row(
    row: dict[str, Any],
    *,
    environment_name: str,
    settings: Settings,
) -> dict[str, Any]:
    conn = None
    config: dict[str, Any] = {}
    if row.get("connection_string_encrypted") and settings.encryption_key:
        try:
            conn = decrypt_value(row["connection_string_encrypted"], settings.encryption_key)
            config = config_from_encrypted_blob(conn)
        except Exception:
            conn = None
            config = {}
    metadata = row.get("metadata") or {}
    if isinstance(metadata, dict):
        record_count = metadata.get("recordCount") or metadata.get("recordsCount") or metadata.get("records") or 0
        type_id = metadata.get("typeId") or metadata.get("source_type_id")
    else:
        record_count = 0
        type_id = None
    return {
        "id": str(row["id"]),
        "name": row.get("name") or row.get("title") or "",
        "type": row.get("type"),
        "typeId": type_id,
        "status": row.get("status") or "connected",
        "environment": row.get("environment") or environment_name,
        "tablesCount": row.get("tables_count") or metadata.get("tablesCount") if isinstance(metadata, dict) else 0,
        "recordCount": record_count,
        "lastSyncAt": row.get("last_sync_at") or row.get("updated_at") or row.get("created_at"),
        "createdAt": row.get("created_at"),
        "description": metadata.get("description") if isinstance(metadata, dict) else None,
        "syncIntervalSeconds": metadata.get("syncIntervalSeconds") if isinstance(metadata, dict) else None,
        "connectionHost": config.get("host"),
        "connectionPort": config.get("port"),
        "connectionDatabase": config.get("database") or config.get("dataset"),
        "connectorId": config.get("connector_id"),
        "connectionString": _mask_connection(conn if isinstance(conn, str) and "{" not in conn else None),
        "config": {k: v for k, v in config.items() if k not in {"password", "secret_access_key", "api_key", "access_token", "credentials_json"}},
    }


@router.get("/types")
async def list_source_types_route(
    _user: Annotated[dict, Depends(get_current_user)],
    category: Annotated[str | None, Query(alias="category")] = None,
    search: Annotated[str | None, Query()] = None,
) -> dict:
    items = list_source_types(category=category, search=search)  # type: ignore[arg-type]
    return {"types": items, "categories": [{"id": key, "label": label} for key, label in CATEGORY_LABELS.items()]}


@router.get("/connectors")
async def list_source_connectors_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    vendor: Annotated[str, Query()],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    connectors = list_connectors_for_vendor(client, org_id, environment=environment_name, oauth_vendor=vendor)
    return {"connectors": connectors}


@router.post("/test")
async def test_source_connection_route(
    body: SourceTestRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    config = dict(body.config or {})
    if body.connection_string:
        config.setdefault("connection_string", body.connection_string)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key) if org_id else None
    try:
        result = await run_connection_test(
            body.type_id,
            config,
            client=client,
            org_id=org_id,
            environment=environment_name,
        )
        schema = await discover_schema(body.type_id, config)
        suggestions = suggest_exploration_questions(schema)
        return {
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "tables": result.get("tables", 0),
            "records": result.get("records", 0),
            "driverPending": result.get("driverPending", False),
            "schemaPreview": (schema.get("tables") or [])[:5],
            "suggestions": suggestions[:5],
        }
    except ConnectionTestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(str(exc), getattr(exc, "code", "CONNECTION_FAILED")),
        ) from exc


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
    try:
        r = (
            client.table("rag_sources")
            .select("id, title, name, type, status, environment, tables_count, last_sync_at, connection_string_encrypted, metadata, created_at, updated_at")
            .eq("org_id", org_id)
            .eq("environment", environment_name)
            .is_("deleted_at", "null")
            .order("updated_at", desc=True)
            .execute()
        )
    except Exception:
        try:
            r = (
                client.table("rag_sources")
                .select("id, title, name, type, status, metadata, created_at, updated_at")
                .eq("org_id", org_id)
                .order("updated_at", desc=True)
                .execute()
            )
        except Exception:
            return {"sources": []}
    items = [_serialize_source_row(row, environment_name=environment_name, settings=settings) for row in list(r.data or [])]
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
    return {"source": _serialize_source_row(source, environment_name=environment_name, settings=settings)}


@router.get("/{source_id}/sync-history")
async def get_source_sync_history_route(
    source_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    history = list_source_sync_history(client, org_id, str(source_id), limit=limit)
    return {"history": history}


@router.post("/{source_id}/test")
async def test_existing_source_route(
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
    metadata = source.get("metadata") or {}
    type_id = str((metadata.get("typeId") if isinstance(metadata, dict) else None) or source.get("type") or "").lower()
    if not settings.encryption_key or not source.get("connection_string_encrypted"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source has no stored connection config")
    raw = decrypt_value(source["connection_string_encrypted"], settings.encryption_key)
    config = config_from_encrypted_blob(raw)
    try:
        result = await run_connection_test(
            type_id,
            config,
            client=client,
            org_id=org_id,
            environment=environment_name,
        )
        schema = await discover_schema(type_id, config)
        return {
            **result,
            "schemaPreview": (schema.get("tables") or [])[:5],
            "suggestions": suggest_exploration_questions(schema)[:5],
        }
    except ConnectionTestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{source_id}/schema")
async def get_source_schema_route(
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
    metadata = source.get("metadata") or {}
    type_id = str((metadata.get("typeId") if isinstance(metadata, dict) else None) or source.get("type") or "").lower()
    if not settings.encryption_key or not source.get("connection_string_encrypted"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source has no stored connection config")
    raw = decrypt_value(source["connection_string_encrypted"], settings.encryption_key)
    config = config_from_encrypted_blob(raw)
    try:
        schema = await discover_schema(type_id, config)
        return schema
    except ConnectionTestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{source_id}/query")
async def query_source_route(
    source_id: UUID,
    body: SourceQueryRequest,
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
    metadata = source.get("metadata") or {}
    type_id = str((metadata.get("typeId") if isinstance(metadata, dict) else None) or source.get("type") or "").lower()
    if not settings.encryption_key or not source.get("connection_string_encrypted"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source has no stored connection config")
    raw = decrypt_value(source["connection_string_encrypted"], settings.encryption_key)
    config = config_from_encrypted_blob(raw)
    try:
        return await natural_language_query(
            type_id=type_id,
            config=config,
            question=body.question,
            settings=settings,
        )
    except ConnectionTestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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
    type_id = _resolve_type_id(body.type, body.type_id)
    config = _build_config_payload(body, type_id)
    errors = validate_connection_config(type_id, config)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("; ".join(errors), "VALIDATION_ERROR"),
        )
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    saas_errors = validate_saas_connector_link(
        client,
        org_id,
        type_id=type_id,
        config=config,
        environment=environment_name,
    )
    if saas_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("; ".join(saas_errors), "VALIDATION_ERROR"),
        )
    encrypted = encrypt_value(json.dumps(config), settings.encryption_key)
    metadata = {
        "typeId": type_id,
        "description": body.description or f"{body.type} data source",
        "recordCount": 0,
        "tablesCount": 0,
        "syncIntervalSeconds": DEFAULT_SYNC_INTERVAL_SECONDS,
    }
    row = {
        "org_id": org_id,
        "title": body.name,
        "name": body.name,
        "type": body.type,
        "status": "connected",
        "connection_string_encrypted": encrypted,
        "environment": environment_name,
        "metadata": metadata,
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
        metadata={"environment": environment_name, "typeId": type_id},
    )
    return {"id": source_id, "typeId": type_id}


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
    if body.connection_string is not None or body.config is not None:
        if not settings.encryption_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_detail("ENCRYPTION_KEY not configured", "INVALID_CONFIG"),
            )
        existing = get_source(
            create_client(settings.supabase_url, settings.supabase_service_role_key),
            org_id,
            str(source_id),
            environment_name=environment_name,
        )
        metadata = (existing or {}).get("metadata") or {}
        type_id = str((metadata.get("typeId") if isinstance(metadata, dict) else None) or (existing or {}).get("type") or "postgresql")
        merged = dict(body.config or {})
        if body.connection_string:
            merged["connection_string"] = body.connection_string
        config = serialize_connection_config(type_id, merged)
        payload["connection_string_encrypted"] = encrypt_value(json.dumps(config), settings.encryption_key)
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
        .select("id, org_id, status, metadata, type, connection_string_encrypted, tables_count, last_sync_at, environment")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(source_id))
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not source.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    result = await sync_source_row(
        client,
        settings,
        org_id=org_id,
        row=source.data[0],
        environment=environment_name,
        actor_id=_user["user_id"],
        trigger="manual",
        full_sync=bool(body.full_sync),
    )
    return result
