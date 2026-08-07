"""Admin API for Google Analytics property linking (STA-40)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.google_analytics import GoogleAnalyticsAPIError, list_ga4_properties
from app.connectors.google_analytics_oauth import link_ga4_property, normalize_vendor
from app.connectors.google_vendor_oauth import ensure_google_vendor_session
from app.core.safe_dict import safe_normalize_stored_dict

router = APIRouter(prefix="/api/connectors", tags=["google-analytics"])


class Ga4PropertyLinkRequest(BaseModel):
    property_id: str = Field(..., alias="propertyId", min_length=1)
    property_name: str | None = Field(default=None, alias="propertyName")
    property_resource: str | None = Field(default=None, alias="propertyResource")

    model_config = {"populate_by_name": True}


def _load_ga_connector(client: Any, org_id: str, connector_id: str) -> dict[str, Any]:
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
    vendor = normalize_vendor(str(connector.get("vendor") or connector.get("type") or ""))
    if vendor != "google_analytics":
        raise HTTPException(status_code=400, detail="Not a Google Analytics connector")
    return connector


@router.get("/{connector_id}/google-analytics/properties")
async def list_google_analytics_properties(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    connector = _load_ga_connector(client, org_id, connector_id)
    env = connector.get("environment") or "production"
    token, err = ensure_google_vendor_session(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "OAuth not connected")
    try:
        properties = list_ga4_properties(token)
    except GoogleAnalyticsAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    config = safe_normalize_stored_dict(connector, key="config")
    return {
        "connectorId": connector_id,
        "properties": properties,
        "linkedPropertyId": config.get("property_id") or config.get("propertyId"),
        "linkedPropertyName": config.get("property_name") or config.get("propertyName"),
    }


@router.put("/{connector_id}/google-analytics/property")
async def link_google_analytics_property(
    connector_id: str,
    body: Ga4PropertyLinkRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_ga_connector(client, org_id, connector_id)
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
        available = list_ga4_properties(token)
    except GoogleAnalyticsAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    match = next((p for p in available if str(p.get("property_id")) == body.property_id), None)
    if not match:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Property not found for this account")

    link_ga4_property(
        client,
        org_id,
        connector_id,
        property_id=body.property_id,
        property_name=body.property_name or match.get("display_name"),
        property_resource=body.property_resource or match.get("property_resource"),
    )
    return {
        "connectorId": connector_id,
        "propertyId": body.property_id,
        "propertyName": body.property_name or match.get("display_name"),
        "status": "linked",
    }
