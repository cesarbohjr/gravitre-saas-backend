"""Admin API for Notion → RAG sync (STA-43)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.notion_oauth import normalize_vendor
from app.services.notion_sync_service import (
    get_notion_sync_status,
    run_notion_sync,
    search_notion,
    set_notion_sync_config,
)

router = APIRouter(prefix="/api/connectors", tags=["notion-sync"])


class NotionSyncTarget(BaseModel):
    id: str
    type: str = Field(default="page", description="page or database")
    title: str | None = None


class NotionSyncUpdate(BaseModel):
    targets: list[NotionSyncTarget] | None = None
    department_id: str | None = Field(default=None, alias="departmentId")

    model_config = {"populate_by_name": True}


class NotionSyncRunRequest(BaseModel):
    full_sync: bool = Field(default=False, alias="fullSync")

    model_config = {"populate_by_name": True}


def _load_notion_connector(client: Any, org_id: str, connector_id: str) -> dict[str, Any]:
    row = (
        client.table("connectors")
        .select("id,type,config,name,environment")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Connector not found")
    connector = dict(row.data[0])
    if normalize_vendor(str(connector.get("type") or "")) != "notion":
        raise HTTPException(status_code=400, detail="Not a Notion connector")
    return connector


@router.get("/{connector_id}/notion-sync")
async def get_notion_sync(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    connector = _load_notion_connector(client, org_id, connector_id)
    status_payload = get_notion_sync_status(connector)
    return {"connector_id": connector_id, **status_payload}


@router.put("/{connector_id}/notion-sync")
async def update_notion_sync(
    connector_id: str,
    body: NotionSyncUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_notion_connector(client, org_id, connector_id)
    targets = None
    if body.targets is not None:
        targets = [t.model_dump() for t in body.targets]
    saved = set_notion_sync_config(
        client,
        org_id,
        connector_id,
        targets=targets,
        department_id=body.department_id,
    )
    return {"connector_id": connector_id, **saved}


@router.get("/{connector_id}/notion-sync/search")
async def notion_sync_search(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    q: str | None = Query(default=None),
    object_type: str | None = Query(default=None, alias="type"),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_notion_connector(client, org_id, connector_id)
    try:
        results = search_notion(
            client,
            org_id,
            connector_id,
            settings,
            query=q,
            filter_object=object_type if object_type in {"page", "database"} else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"connector_id": connector_id, "results": results}


@router.post("/{connector_id}/notion-sync/run")
async def notion_sync_run(
    connector_id: str,
    body: NotionSyncRunRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_notion_connector(client, org_id, connector_id)
    try:
        result = run_notion_sync(
            client,
            org_id,
            connector_id,
            settings,
            actor_id=str(user["user_id"]),
            full_sync=body.full_sync,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"connector_id": connector_id, **result}
