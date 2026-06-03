"""Connector OAuth start/callback routes (STA-13)."""
from __future__ import annotations

import time
from typing import Annotated
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from supabase import create_client

import httpx

from app.auth.dependencies import get_environment_context, require_admin
from app.billing.service import ADVANCED_CONNECTORS, get_plan_for_org, require_feature
from app.config import Settings, get_settings
from app.connectors.hubspot_oauth import (
    complete_hubspot_oauth_connection,
    hubspot_authorize_url,
    hubspot_credentials,
    hubspot_oauth_configured,
    hubspot_redirect_uri,
    normalize_vendor,
)
from app.connectors.salesforce_oauth import (
    complete_salesforce_oauth_connection,
    salesforce_authorize_url,
    salesforce_credentials,
    salesforce_oauth_configured,
    salesforce_redirect_uri,
    normalize_vendor as normalize_salesforce_vendor,
)
from app.connectors.oauth_state import sign_oauth_state, verify_oauth_state
from app.core.errors import error_detail
from app.middleware.entitlements import resolve_entitlements
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/connectors/oauth", tags=["connector-oauth"])

SUPPORTED_OAUTH_PROVIDERS = frozenset({"hubspot", "salesforce"})


class OAuthStartRequest(BaseModel):
    name: str = Field(..., min_length=1)
    connector_id: str | None = Field(default=None, alias="connectorId")
    redirect_path: str | None = Field(default="/connectors", alias="redirectPath")

    model_config = {"populate_by_name": True}


class OAuthStartResponse(BaseModel):
    authorization_url: str = Field(alias="authorizationUrl")
    connector_id: str = Field(alias="connectorId")
    state: str

    model_config = {"populate_by_name": True}


class OAuthProviderStatusResponse(BaseModel):
    provider: str
    configured: bool
    encryption_configured: bool = Field(alias="encryptionConfigured")
    redirect_uri: str | None = Field(default=None, alias="redirectUri")

    model_config = {"populate_by_name": True}


def _oauth_state_secret(settings: Settings) -> str:
    secret = (settings.connector_secrets_encryption_key or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connector secrets encryption not configured",
        )
    return secret


def _frontend_redirect(settings: Settings, path: str, params: dict[str, str]) -> str:
    base = (settings.public_app_url or "http://localhost:3000").rstrip("/")
    safe_path = path if path.startswith("/") else f"/{path}"
    query = urlencode(params)
    return f"{base}{safe_path}?{query}" if query else f"{base}{safe_path}"


@router.get("/{provider}/status", response_model=OAuthProviderStatusResponse)
async def oauth_provider_status(
    provider: str,
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OAuthProviderStatusResponse:
    """Public readiness check for platform OAuth (no secrets)."""
    vendor = normalize_vendor(provider)
    if vendor == "salesforce":
        vendor = normalize_salesforce_vendor(provider)
    if vendor not in SUPPORTED_OAUTH_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported OAuth provider")

    configured = False
    redirect_uri: str | None = None
    if vendor == "hubspot":
        configured = hubspot_oauth_configured(settings, environment_name)
        redirect_uri = hubspot_redirect_uri(settings)
    elif vendor == "salesforce":
        configured = salesforce_oauth_configured(settings, environment_name)
        redirect_uri = salesforce_redirect_uri(settings)

    return OAuthProviderStatusResponse(
        provider=vendor,
        configured=configured,
        encryption_configured=bool((settings.connector_secrets_encryption_key or "").strip()),
        redirect_uri=redirect_uri,
    )


@router.post("/{provider}/start", response_model=OAuthStartResponse)
async def start_oauth(
    provider: str,
    body: OAuthStartRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OAuthStartResponse:
    """Create (or reuse) a connector and return the provider authorization URL."""
    _user, org_id = _admin
    vendor = normalize_vendor(provider)
    if vendor == "hubspot":
        pass
    elif normalize_salesforce_vendor(provider) == "salesforce":
        vendor = "salesforce"
    if vendor not in SUPPORTED_OAUTH_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported OAuth provider")

    if vendor == "hubspot" and not hubspot_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("HubSpot OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor == "salesforce" and not salesforce_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Salesforce OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    entitlements = resolve_entitlements(settings, org_id)
    if vendor in ADVANCED_CONNECTORS:
        plan = get_plan_for_org(client, org_id)
        require_feature(plan, "advanced_connectors")
        features = plan.get("features") or {}
        if not features.get("advanced_connectors"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_detail("Upgrade required", "UNAUTHORIZED", {"feature": "advanced_connectors"}),
            )

    connector_id = body.connector_id
    reconnect = bool(body.connector_id)
    if connector_id:
        existing = (
            client.table("connectors")
            .select("id, vendor")
            .eq("org_id", org_id)
            .eq("id", connector_id)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
        if normalize_vendor(existing.data[0].get("vendor") or "") != vendor:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connector vendor mismatch")
    else:
        row = {
            "org_id": org_id,
            "name": body.name.strip(),
            "vendor": vendor,
            "type": vendor,
            "description": f"{vendor.title()} (OAuth)",
            "status": "pending_auth",
            "environment": environment_name,
            "sync_frequency": "1h",
            "config": {"auth_type": "oauth"},
            "docs_url": (
                "https://developers.hubspot.com/docs"
                if vendor == "hubspot"
                else "https://developer.salesforce.com/docs"
            ),
        }
        created = client.table("connectors").insert(row).execute()
        if not created.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Connector create failed")
        connector_id = str(created.data[0]["id"])
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=_user["user_id"],
            action="connector.created",
            resource_type="connector",
            resource_id=connector_id,
            metadata={"environment": environment_name, "auth": "oauth"},
        )

    now = time.time()
    state = sign_oauth_state(
        {
            "org_id": org_id,
            "user_id": _user["user_id"],
            "connector_id": connector_id,
            "provider": vendor,
            "environment": environment_name,
            "redirect_path": body.redirect_path or "/connectors",
            "reconnect": reconnect,
            "iat": now,
            "exp": now + 600,
        },
        _oauth_state_secret(settings),
    )

    auth_url = ""
    if vendor == "hubspot":
        redirect_uri = hubspot_redirect_uri(settings)
        client_id, _secret = hubspot_credentials(settings, environment_name)
        auth_url = hubspot_authorize_url(client_id, redirect_uri, state)
    elif vendor == "salesforce":
        redirect_uri = salesforce_redirect_uri(settings)
        client_id, _secret = salesforce_credentials(settings, environment_name)
        auth_url = salesforce_authorize_url(
            client_id, redirect_uri, state, environment_name=environment_name
        )

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="connector.oauth.reconnect_started" if reconnect else "connector.oauth.started",
        resource_type="connector",
        resource_id=connector_id,
        metadata={"provider": vendor, "environment": environment_name},
    )
    return OAuthStartResponse(authorization_url=auth_url, connector_id=connector_id, state=state)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    settings: Annotated[Settings, Depends(get_settings)],
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None, alias="error_description"),
) -> RedirectResponse:
    """OAuth callback (browser redirect). Exchanges code and stores encrypted tokens."""
    vendor = normalize_vendor(provider)
    if vendor != "hubspot" and normalize_salesforce_vendor(provider) == "salesforce":
        vendor = "salesforce"
    default_fail = _frontend_redirect(settings, "/connectors", {"oauth": "error", "provider": vendor})

    if error:
        params = {"oauth": "error", "provider": vendor, "message": error_description or error}
        return RedirectResponse(_frontend_redirect(settings, "/connectors", params), status_code=302)

    if not code or not state:
        return RedirectResponse(default_fail, status_code=302)

    try:
        payload = verify_oauth_state(state, _oauth_state_secret(settings))
    except ValueError as exc:
        return RedirectResponse(
            _frontend_redirect(settings, "/connectors", {"oauth": "error", "message": str(exc)}),
            status_code=302,
        )

    if payload.get("provider") != vendor:
        return RedirectResponse(default_fail, status_code=302)

    org_id = str(payload["org_id"])
    connector_id = str(payload["connector_id"])
    redirect_path = str(payload.get("redirect_path") or "/connectors")
    environment_name = str(payload.get("environment") or "production")
    reconnect = bool(payload.get("reconnect"))
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    try:
        if vendor == "hubspot":
            complete_hubspot_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                environment_name=environment_name,
                reconnect=reconnect,
            )
        elif vendor == "salesforce":
            complete_salesforce_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                environment_name=environment_name,
                reconnect=reconnect,
            )
    except (httpx.HTTPError, ValueError):
        return RedirectResponse(
            _frontend_redirect(
                redirect_path,
                {"oauth": "error", "provider": vendor, "message": "token_exchange_failed"},
            ),
            status_code=302,
        )

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=str(payload.get("user_id") or org_id),
        action="connector.oauth.reconnected" if reconnect else "connector.oauth.completed",
        resource_type="connector",
        resource_id=connector_id,
        metadata={"provider": vendor, "environment": environment_name},
    )

    return RedirectResponse(
        _frontend_redirect(
            redirect_path,
            {"oauth": "success", "provider": vendor, "connectorId": connector_id},
        ),
        status_code=302,
    )
