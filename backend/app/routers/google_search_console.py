"""Admin API for Google Search Console site linking (Marketing #6)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.google_search_console import GoogleSearchConsoleAPIError, list_gsc_sites
from app.connectors.google_search_console_oauth import link_gsc_site, normalize_gsc_vendor
from app.connectors.google_vendor_oauth import ensure_google_vendor_session
from app.core.safe_dict import safe_normalize_stored_dict

router = APIRouter(prefix="/api/connectors", tags=["google-search-console"])


class GscSiteLinkRequest(BaseModel):
    site_url: str = Field(..., alias="siteUrl", min_length=1)
    permission_level: str | None = Field(default=None, alias="permissionLevel")

    model_config = {"populate_by_name": True}


def _load_gsc_connector(client: Any, org_id: str, connector_id: str) -> dict[str, Any]:
    row = (
        client.table("connectors")
        .select("id,type,vendor,config,name,environment")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Connector not found")
    connector = dict(row.data[0])
    vendor = normalize_gsc_vendor(str(connector.get("vendor") or connector.get("type") or ""))
    if vendor != "google_search_console":
        raise HTTPException(status_code=400, detail="Not a Google Search Console connector")
    return connector


@router.get("/{connector_id}/google-search-console/sites")
async def list_google_search_console_sites(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    connector = _load_gsc_connector(client, org_id, connector_id)
    env = connector.get("environment") or "production"
    token, err = ensure_google_vendor_session(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "OAuth not connected")
    try:
        sites = list_gsc_sites(token)
    except GoogleSearchConsoleAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    config = safe_normalize_stored_dict(connector, key="config")
    return {
        "connectorId": connector_id,
        "sites": sites,
        "linkedSiteUrl": config.get("site_url") or config.get("siteUrl"),
        "linkedPermissionLevel": config.get("permission_level") or config.get("permissionLevel"),
    }


@router.put("/{connector_id}/google-search-console/site")
async def link_google_search_console_site(
    connector_id: str,
    body: GscSiteLinkRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_gsc_connector(client, org_id, connector_id)
    env_row = (
        client.table("connectors")
        .select("environment")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    env = (env_row.data or [{}])[0].get("environment") or "production"
    token, err = ensure_google_vendor_session(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "OAuth not connected")

    try:
        available = list_gsc_sites(token)
    except GoogleSearchConsoleAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    match = next((s for s in available if str(s.get("site_url")) == body.site_url), None)
    if not match:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Site not found for this account")

    link_gsc_site(
        client,
        org_id,
        connector_id,
        site_url=body.site_url,
        permission_level=body.permission_level or match.get("permission_level"),
    )
    return {
        "connectorId": connector_id,
        "siteUrl": body.site_url,
        "permissionLevel": body.permission_level or match.get("permission_level"),
        "status": "linked",
    }
