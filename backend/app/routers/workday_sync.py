"""Admin API for Workday HR → RAG sync (STA-61)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.workday_oauth import normalize_vendor
from app.services.workday_sync_service import (
    get_workday_sync_status,
    run_workday_sync,
    search_workday_policy_content,
    set_workday_sync_config,
)

router = APIRouter(prefix="/api/connectors", tags=["workday-sync"])


class WorkdaySyncTarget(BaseModel):
    id: str
    type: str = Field(default="policy", description="policy")
    title: str | None = None


class WorkdaySyncUpdate(BaseModel):
    targets: list[WorkdaySyncTarget] | None = None
    department_id: str | None = Field(default=None, alias="departmentId")

    model_config = {"populate_by_name": True}


class WorkdaySyncRunRequest(BaseModel):
    full_sync: bool = Field(default=False, alias="fullSync")

    model_config = {"populate_by_name": True}


def _load_workday_connector(client: Any, org_id: str, connector_id: str) -> dict[str, Any]:
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
    if normalize_vendor(str(connector.get("type") or "")) != "workday":
        raise HTTPException(status_code=400, detail="Not a Workday connector")
    return connector


@router.get("/{connector_id}/workday-sync")
async def get_workday_sync(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    connector = _load_workday_connector(client, org_id, connector_id)
    status_payload = get_workday_sync_status(connector)
    return {"connector_id": connector_id, **status_payload}


@router.put("/{connector_id}/workday-sync")
async def update_workday_sync(
    connector_id: str,
    body: WorkdaySyncUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_workday_connector(client, org_id, connector_id)
    targets = None
    if body.targets is not None:
        targets = [t.model_dump() for t in body.targets]
    saved = set_workday_sync_config(
        client,
        org_id,
        connector_id,
        targets=targets,
        department_id=body.department_id,
    )
    return {"connector_id": connector_id, **saved}


@router.get("/{connector_id}/workday-sync/search")
async def workday_sync_search(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    q: str | None = Query(default=None),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_workday_connector(client, org_id, connector_id)
    try:
        results = search_workday_policy_content(
            client,
            org_id,
            connector_id,
            settings,
            query=q,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"connector_id": connector_id, "results": results}


@router.post("/{connector_id}/workday-sync/run")
async def workday_sync_run(
    connector_id: str,
    body: WorkdaySyncRunRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    user: Annotated[dict, Depends(get_current_user)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_workday_connector(client, org_id, connector_id)
    try:
        result = run_workday_sync(
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
