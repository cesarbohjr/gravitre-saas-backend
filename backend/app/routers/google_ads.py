"""Admin API for Google Ads customer linking."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.google_ads import GoogleAdsAPIError, list_accessible_customers
from app.connectors.google_ads_oauth import link_google_ads_customer, normalize_google_ads_vendor
from app.connectors.google_vendor_oauth import ensure_google_vendor_session

router = APIRouter(prefix="/api/connectors", tags=["google-ads"])


class GoogleAdsCustomerLinkRequest(BaseModel):
    customer_id: str = Field(..., alias="customerId", min_length=6)
    login_customer_id: str | None = Field(default=None, alias="loginCustomerId")
    descriptive_name: str | None = Field(default=None, alias="descriptiveName")

    model_config = {"populate_by_name": True}


def _load_ads_connector(client: Any, org_id: str, connector_id: str) -> dict[str, Any]:
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
    vendor = normalize_google_ads_vendor(str(connector.get("vendor") or connector.get("type") or ""))
    if vendor != "google_ads":
        raise HTTPException(status_code=400, detail="Not a Google Ads connector")
    return connector


@router.get("/{connector_id}/google-ads/customers")
async def list_google_ads_customers(
    connector_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    connector = _load_ads_connector(client, org_id, connector_id)
    env = connector.get("environment") or "production"
    token, err = ensure_google_vendor_session(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "OAuth not connected")
    developer_token = (getattr(settings, "google_ads_developer_token", None) or "").strip()
    if not developer_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Google Ads developer token is not configured on the API. "
                "Set GOOGLE_ADS_DEVELOPER_TOKEN (requires a Google Ads Manager account + API Center)."
            ),
        )
    try:
        customers = list_accessible_customers(token, developer_token=developer_token)
    except GoogleAdsAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    config = dict(connector.get("config") or {})
    return {
        "connectorId": connector_id,
        "customers": customers,
        "linkedCustomerId": config.get("customer_id") or config.get("customerId"),
        "loginCustomerId": config.get("login_customer_id") or config.get("loginCustomerId"),
        "developerTokenConfigured": True,
    }


@router.put("/{connector_id}/google-ads/customer")
async def link_google_ads_customer_route(
    connector_id: str,
    body: GoogleAdsCustomerLinkRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _load_ads_connector(client, org_id, connector_id)
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
    developer_token = (getattr(settings, "google_ads_developer_token", None) or "").strip()
    if not developer_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GOOGLE_ADS_DEVELOPER_TOKEN is not configured",
        )
    try:
        available = list_accessible_customers(token, developer_token=developer_token)
    except GoogleAdsAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    wanted = body.customer_id.strip().replace("-", "")
    if wanted not in {c["customer_id"] for c in available}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="customer_id is not in the accessible customer list for this Google account",
        )
    link_google_ads_customer(
        client,
        org_id,
        connector_id,
        customer_id=wanted,
        login_customer_id=body.login_customer_id,
        descriptive_name=body.descriptive_name,
    )
    return {
        "connectorId": connector_id,
        "customerId": wanted,
        "loginCustomerId": (body.login_customer_id or "").replace("-", "") or None,
        "status": "connected",
    }
