"""Admin API for Confluence → RAG sync (STA-44)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.confluence_oauth import normalize_vendor
from app.services.confluence_sync_service import (
    get_confluence_sync_status,
    run_confluence_sync,
    search_confluence_spaces,
    set_confluence_sync_config,
)

router = APIRouter(prefix="/api/connectors", tags=["confluence-sync"])


class ConfluenceSyncTarget(BaseModel):
    id: str
    type: str = Field(default="space", description="space")
    title: str | None = None
    key: str | None = None


class ConfluenceSyncUpdate(BaseModel):
    targets: list[ConfluenceSyncTarget] | None = None
    department_id: str | None = Field(default=None, alias="departmentId")

    model_config = {"populate_by_name": True}


class ConfluenceSyncRunRequest(BaseModel):
    full_sync: bool = Field(default=False, alias="fullSync")

    model_config = {"populate_by_name": True}


def _load_confluence_connector(client: Any, org_id: str, connector_id: str) -> dict[str, Any]:
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
    if normalize_vendor(str(connector.get("type") or "")) != "confluence":
        raise HTTPException(status_code=400, detail="Not a Confluence connector")
    return connector


@router.get("/{connector_id}/confluence-sync")
async def get_confluence_sync(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    connector = _load_confluence_connector(client, org_id, connector_id)
    status_payload = get_confluence_sync_status(connector)
    return {"connector_id": connector_id, **status_payload}


@router.put("/{connector_id}/confluence-sync")
async def update_confluence_sync(
    connector_id: str,
    body: ConfluenceSyncUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_confluence_connector(client, org_id, connector_id)
    targets = None
    if body.targets is not None:
        targets = [t.model_dump() for t in body.targets]
    saved = set_confluence_sync_config(
        client,
        org_id,
        connector_id,
        targets=targets,
        department_id=body.department_id,
    )
    return {"connector_id": connector_id, **saved}


@router.get("/{connector_id}/confluence-sync/search")
async def confluence_sync_search(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    q: str | None = Query(default=None),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_confluence_connector(client, org_id, connector_id)
    try:
        results = search_confluence_spaces(
            client,
            org_id,
            connector_id,
            settings,
            query=q,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"connector_id": connector_id, "results": results}


@router.post("/{connector_id}/confluence-sync/run")
async def confluence_sync_run(
    connector_id: str,
    body: ConfluenceSyncRunRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_confluence_connector(client, org_id, connector_id)
    try:
        result = run_confluence_sync(
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
