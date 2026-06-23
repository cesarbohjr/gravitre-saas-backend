"""Knowledge sync scheduler API (STA-45)."""
from __future__ import annotations

import asyncio
import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_org_context, require_admin, require_org_member
from app.auth.platform_admin import can_trigger_knowledge_sync, is_org_admin_role
from app.config import Settings, get_settings
from app.connectors.notion_oauth import normalize_vendor
from app.services.knowledge_sync_service import (
    list_recent_sync_jobs,
    run_scheduled_knowledge_syncs,
    trigger_connector_knowledge_sync,
)

internal_router = APIRouter(prefix="/api/internal/knowledge", tags=["knowledge-internal"])
admin_router = APIRouter(prefix="/api/admin/knowledge", tags=["knowledge-admin"])
customer_router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
webhook_router = APIRouter(prefix="/api/webhooks/knowledge", tags=["knowledge-webhooks"])


async def require_internal_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_secret: Annotated[str | None, Header()] = None,
) -> None:
    secret = (settings.internal_api_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_API_SECRET is not configured",
        )
    if not x_internal_secret or not hmac.compare_digest(x_internal_secret, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret")


@internal_router.post("/sync-due")
async def internal_sync_due(
    _secret: Annotated[None, Depends(require_internal_secret)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Cron entry: run all due knowledge syncs (Notion, etc.)."""
    summary = await asyncio.to_thread(run_scheduled_knowledge_syncs, settings)
    return summary


class KnowledgeSyncRunRequest(BaseModel):
    full_sync: bool = Field(default=False, alias="fullSync")

    model_config = {"populate_by_name": True}


@admin_router.get("/sync-jobs")
async def admin_list_sync_jobs(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    connector_id: str | None = Query(default=None, alias="connectorId"),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    return await _list_sync_jobs_handler(org_id, settings, connector_id=connector_id, limit=limit)


@admin_router.post("/connectors/{connector_id}/sync")
async def admin_trigger_connector_sync(
    connector_id: str,
    body: KnowledgeSyncRunRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    user_admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, _org = user_admin
    return await _trigger_connector_sync_handler(
        connector_id,
        org_id,
        str(user["user_id"]),
        settings,
        full_sync=body.full_sync,
    )


async def _list_sync_jobs_handler(
    org_id: str,
    settings: Settings,
    *,
    connector_id: str | None,
    limit: int,
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    jobs = list_recent_sync_jobs(client, org_id, limit=limit, connector_id=connector_id)
    return {"jobs": jobs}


async def _trigger_connector_sync_handler(
    connector_id: str,
    org_id: str,
    user_id: str,
    settings: Settings,
    *,
    full_sync: bool,
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        result = await asyncio.to_thread(
            trigger_connector_knowledge_sync,
            client,
            settings,
            org_id,
            connector_id,
            actor_id=user_id,
            trigger_type="manual",
            full_sync=full_sync,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"connector_id": connector_id, **result}


@customer_router.get("/sync-jobs")
async def customer_list_sync_jobs(
    member_ctx: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
    connector_id: str | None = Query(default=None, alias="connectorId"),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    """Org member knowledge sync history (product path — STA-279)."""
    _user, org_id, _role = member_ctx
    return await _list_sync_jobs_handler(org_id, settings, connector_id=connector_id, limit=limit)


@customer_router.post("/connectors/{connector_id}/sync")
async def customer_trigger_connector_sync(
    connector_id: str,
    body: KnowledgeSyncRunRequest,
    member_ctx: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Org member manual knowledge sync; full sync requires admin (STA-279)."""
    user, org_id, role = member_ctx
    if not can_trigger_knowledge_sync(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewer role cannot trigger knowledge sync",
        )
    if body.full_sync and not is_org_admin_role(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Full sync requires workspace admin role",
        )
    return await _trigger_connector_sync_handler(
        connector_id,
        org_id,
        str(user["user_id"]),
        settings,
        full_sync=body.full_sync,
    )


@webhook_router.post("/{connector_id}/sync")
async def webhook_trigger_sync(
    connector_id: str,
    settings: Settings = Depends(get_settings),
    x_webhook_secret: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Webhook-on-publish hook: enqueue immediate knowledge sync for a connector."""
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        client.table("connectors")
        .select("id,org_id,type,config,status")
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Connector not found")
    connector = dict(row.data[0])
    if str(connector.get("status") or "") != "active":
        raise HTTPException(status_code=400, detail="Connector not active")
    vendor = normalize_vendor(str(connector.get("type") or ""))
    if vendor != "notion":
        raise HTTPException(status_code=400, detail="Webhook sync only supported for Notion in v1")

    config = connector.get("config") or {}
    expected = str(
        config.get("knowledge_webhook_secret")
        or config.get("webhook_secret")
        or ""
    ).strip()
    if expected:
        if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    org_id = str(connector["org_id"])
    try:
        result = await asyncio.to_thread(
            trigger_connector_knowledge_sync,
            client,
            settings,
            org_id,
            connector_id,
            actor_id="system",
            trigger_type="webhook",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"connector_id": connector_id, "trigger": "webhook", **result}
