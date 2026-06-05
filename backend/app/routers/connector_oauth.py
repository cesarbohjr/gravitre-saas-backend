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
from app.connectors.quickbooks_oauth import (
    complete_quickbooks_oauth_connection,
    quickbooks_authorize_url,
    quickbooks_credentials,
    quickbooks_oauth_configured,
    quickbooks_redirect_uri,
    normalize_vendor as normalize_quickbooks_vendor,
)
from app.connectors.confluence_oauth import (
    complete_confluence_oauth_connection,
    confluence_authorize_url,
    confluence_credentials,
    confluence_oauth_configured,
    confluence_redirect_uri,
    normalize_vendor as normalize_confluence_vendor,
)
from app.connectors.jira_oauth import (
    complete_jira_oauth_connection,
    jira_authorize_url,
    jira_credentials,
    jira_oauth_configured,
    jira_redirect_uri,
    normalize_vendor as normalize_jira_vendor,
)
from app.services.devops_workflow_service import on_pagerduty_connector_connected
from app.connectors.pagerduty_oauth import (
    complete_pagerduty_oauth_connection,
    pagerduty_authorize_url,
    pagerduty_credentials,
    pagerduty_oauth_configured,
    pagerduty_redirect_uri,
    normalize_vendor as normalize_pagerduty_vendor,
)
from app.connectors.notion_oauth import (
    complete_notion_oauth_connection,
    notion_authorize_url,
    notion_credentials,
    notion_oauth_configured,
    notion_redirect_uri,
    normalize_vendor as normalize_notion_vendor,
)
from app.connectors.pagerduty_webhooks import pagerduty_inbound_webhook_url
from app.connectors.salesforce_oauth import (
    complete_salesforce_oauth_connection,
    salesforce_authorize_url,
    salesforce_credentials,
    salesforce_oauth_configured,
    salesforce_redirect_uri,
    normalize_vendor as normalize_salesforce_vendor,
)
from app.connectors.google_vendor_oauth import (
    GOOGLE_OAUTH_VENDORS,
    VENDOR_DOCS as GOOGLE_VENDOR_DOCS,
    complete_google_vendor_oauth_connection,
    google_oauth_configured,
    google_vendor_authorize_url,
    google_vendor_redirect_uri,
    normalize_google_vendor,
)
from app.connectors.google_oauth_common import google_oauth_credentials
from app.connectors.oauth_state import sign_oauth_state, verify_oauth_state
from app.core.errors import error_detail
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/connectors/oauth", tags=["connector-oauth"])

SUPPORTED_OAUTH_PROVIDERS = frozenset(
    {
        "hubspot",
        "salesforce",
        "quickbooks",
        "jira",
        "confluence",
        "pagerduty",
        "notion",
    }
) | GOOGLE_OAUTH_VENDORS


def _resolve_oauth_vendor(provider: str) -> str:
    google = normalize_google_vendor(provider)
    if google:
        return google
    vendor = normalize_vendor(provider)
    if vendor == "hubspot":
        return "hubspot"
    if normalize_salesforce_vendor(provider) == "salesforce":
        return "salesforce"
    if normalize_quickbooks_vendor(provider) == "quickbooks":
        return "quickbooks"
    if normalize_jira_vendor(provider) == "jira":
        return "jira"
    if normalize_confluence_vendor(provider) == "confluence":
        return "confluence"
    if normalize_pagerduty_vendor(provider) == "pagerduty":
        return "pagerduty"
    if normalize_notion_vendor(provider) == "notion":
        return "notion"
    return vendor


class OAuthStartRequest(BaseModel):
    name: str = Field(..., min_length=1)
    connector_id: str | None = Field(default=None, alias="connectorId")
    redirect_path: str | None = Field(default="/connectors", alias="redirectPath")

    model_config = {"populate_by_name": True}  # noqa: RUF012 — pydantic model config


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


def _oauth_docs_url(vendor: str) -> str:
    if vendor in GOOGLE_OAUTH_VENDORS:
        return GOOGLE_VENDOR_DOCS.get(vendor) or ""
    if vendor == "hubspot":
        return "https://developers.hubspot.com/docs"
    if vendor == "salesforce":
        return "https://developer.salesforce.com/docs"
    if vendor == "quickbooks":
        return "https://developer.intuit.com/app/developer/qbo/docs"
    if vendor == "jira":
        return "https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/"
    if vendor == "pagerduty":
        return "https://developer.pagerduty.com/docs/72d3b724589e3-oauth-functionality"
    if vendor == "notion":
        return "https://developers.notion.com/docs/authorization"
    return ""


def _find_existing_oauth_connector(
    client,
    org_id: str,
    vendor: str,
    name: str,
) -> dict | None:
    """Reuse an existing connector row when OAuth is retried (org_id + name is unique)."""
    normalized_name = name.strip()
    by_name = (
        client.table("connectors")
        .select("id, vendor, name, status, environment")
        .eq("org_id", org_id)
        .eq("name", normalized_name)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if by_name.data:
        row = by_name.data[0]
        existing_vendor = normalize_vendor(row.get("vendor") or row.get("type") or "")
        if existing_vendor and existing_vendor != vendor:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_detail(
                    f"A connector named {normalized_name!r} already exists for another integration",
                    "CONNECTOR_NAME_CONFLICT",
                ),
            )
        return row

    by_vendor = (
        client.table("connectors")
        .select("id, vendor, name, status, environment")
        .eq("org_id", org_id)
        .eq("vendor", vendor)
        .is_("deleted_at", "null")
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if by_vendor.data:
        return by_vendor.data[0]
    return None


def _prepare_oauth_connector(
    client,
    *,
    org_id: str,
    vendor: str,
    name: str,
    environment_name: str,
) -> tuple[str, bool, bool]:
    """Create or reuse a pending_auth connector. Returns (connector_id, reconnect, is_new)."""
    docs_url = _oauth_docs_url(vendor)
    existing = _find_existing_oauth_connector(client, org_id, vendor, name)
    if existing:
        connector_id = str(existing["id"])
        prior_status = str(existing.get("status") or "")
        reconnect = prior_status not in {"", "pending_auth", "disconnected"}
        client.table("connectors").update(
            {
                "status": "pending_auth",
                "environment": environment_name,
                "vendor": vendor,
                "type": vendor,
                "description": f"{vendor.title()} (OAuth)",
                "sync_frequency": "1h",
                "config": {"auth_type": "oauth"},
                "docs_url": docs_url,
            }
        ).eq("id", connector_id).eq("org_id", org_id).execute()
        return connector_id, reconnect, False

    row = {
        "org_id": org_id,
        "name": name.strip(),
        "vendor": vendor,
        "type": vendor,
        "description": f"{vendor.title()} (OAuth)",
        "status": "pending_auth",
        "environment": environment_name,
        "sync_frequency": "1h",
        "config": {"auth_type": "oauth"},
        "docs_url": docs_url,
    }
    created = client.table("connectors").insert(row).execute()
    if not created.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Connector create failed")
    return str(created.data[0]["id"]), False, True


@router.get("/{provider}/status", response_model=OAuthProviderStatusResponse)
async def oauth_provider_status(
    provider: str,
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OAuthProviderStatusResponse:
    """Public readiness check for platform OAuth (no secrets)."""
    vendor = _resolve_oauth_vendor(provider)
    if vendor not in SUPPORTED_OAUTH_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported OAuth provider")

    configured = False
    redirect_uri: str | None = None
    if vendor in GOOGLE_OAUTH_VENDORS:
        configured = google_oauth_configured(settings, environment_name)
        redirect_uri = google_vendor_redirect_uri(settings, vendor)
    elif vendor == "hubspot":
        configured = hubspot_oauth_configured(settings, environment_name)
        redirect_uri = hubspot_redirect_uri(settings)
    elif vendor == "salesforce":
        configured = salesforce_oauth_configured(settings, environment_name)
        redirect_uri = salesforce_redirect_uri(settings)
    elif vendor == "quickbooks":
        configured = quickbooks_oauth_configured(settings, environment_name)
        redirect_uri = quickbooks_redirect_uri(settings)
    elif vendor == "jira":
        configured = jira_oauth_configured(settings, environment_name)
        redirect_uri = jira_redirect_uri(settings)
    elif vendor == "confluence":
        configured = confluence_oauth_configured(settings, environment_name)
        redirect_uri = confluence_redirect_uri(settings)
    elif vendor == "pagerduty":
        configured = pagerduty_oauth_configured(settings, environment_name)
        redirect_uri = pagerduty_redirect_uri(settings)
    elif vendor == "notion":
        configured = notion_oauth_configured(settings, environment_name)
        redirect_uri = notion_redirect_uri(settings)

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
    vendor = _resolve_oauth_vendor(provider)
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
    if vendor == "quickbooks" and not quickbooks_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("QuickBooks OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor == "jira" and not jira_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Jira OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor == "confluence" and not confluence_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Confluence OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor == "pagerduty" and not pagerduty_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("PagerDuty OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor == "notion" and not notion_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Notion OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor in GOOGLE_OAUTH_VENDORS and not google_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Google OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    if vendor in ADVANCED_CONNECTORS:
        try:
            plan = get_plan_for_org(client, org_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_detail(f"Billing lookup failed: {exc}", "BILLING_LOOKUP_FAILED"),
            ) from exc
        require_feature(plan, "advanced_connectors")

    connector_id = body.connector_id
    reconnect = bool(body.connector_id)
    if connector_id:
        existing = (
            client.table("connectors")
            .select("id, vendor, type")
            .eq("org_id", org_id)
            .eq("id", connector_id)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
        row = existing.data[0]
        stored_vendor = normalize_vendor(row.get("vendor") or row.get("type") or "")
        if stored_vendor != vendor:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connector vendor mismatch")
        client.table("connectors").update(
            {
                "status": "pending_auth",
                "environment": environment_name,
                "vendor": vendor,
                "type": vendor,
                "config": {"auth_type": "oauth"},
            }
        ).eq("id", connector_id).eq("org_id", org_id).execute()
    else:
        try:
            connector_id, oauth_reconnect, is_new = _prepare_oauth_connector(
                client,
                org_id=org_id,
                vendor=vendor,
                name=body.name,
                environment_name=environment_name,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail(f"Connector create failed: {exc}", "CONNECTOR_CREATE_FAILED"),
            ) from exc
        reconnect = oauth_reconnect
        if is_new:
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
    elif vendor == "quickbooks":
        redirect_uri = quickbooks_redirect_uri(settings)
        client_id, _secret = quickbooks_credentials(settings, environment_name)
        auth_url = quickbooks_authorize_url(
            client_id, redirect_uri, state, environment_name=environment_name
        )
    elif vendor == "jira":
        redirect_uri = jira_redirect_uri(settings)
        client_id, _secret = jira_credentials(settings, environment_name)
        auth_url = jira_authorize_url(client_id, redirect_uri, state)
    elif vendor == "confluence":
        redirect_uri = confluence_redirect_uri(settings)
        client_id, _secret = confluence_credentials(settings, environment_name)
        auth_url = confluence_authorize_url(client_id, redirect_uri, state)
    elif vendor == "pagerduty":
        redirect_uri = pagerduty_redirect_uri(settings)
        client_id, _secret = pagerduty_credentials(settings, environment_name)
        auth_url = pagerduty_authorize_url(client_id, redirect_uri, state)
    elif vendor == "notion":
        redirect_uri = notion_redirect_uri(settings)
        client_id, _secret = notion_credentials(settings, environment_name)
        auth_url = notion_authorize_url(client_id, redirect_uri, state)
    elif vendor in GOOGLE_OAUTH_VENDORS:
        redirect_uri = google_vendor_redirect_uri(settings, vendor)
        client_id, _secret = google_oauth_credentials(settings, environment_name)
        auth_url = google_vendor_authorize_url(vendor, client_id, redirect_uri, state)

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
    realm_id: str | None = Query(default=None, alias="realmId"),
) -> RedirectResponse:
    """OAuth callback (browser redirect). Exchanges code and stores encrypted tokens."""
    vendor = _resolve_oauth_vendor(provider)
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
    property_linked = True

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
        elif vendor == "quickbooks":
            complete_quickbooks_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                realm_id=realm_id,
                environment_name=environment_name,
                reconnect=reconnect,
            )
        elif vendor == "jira":
            complete_jira_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                environment_name=environment_name,
                reconnect=reconnect,
            )
        elif vendor == "confluence":
            complete_confluence_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                environment_name=environment_name,
                reconnect=reconnect,
            )
        elif vendor == "pagerduty":
            inbound_url = pagerduty_inbound_webhook_url(settings, connector_id)
            complete_pagerduty_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                environment_name=environment_name,
                reconnect=reconnect,
                inbound_webhook_url=inbound_url,
            )
            on_pagerduty_connector_connected(client, org_id, connector_id, settings)
        elif vendor == "notion":
            complete_notion_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                environment_name=environment_name,
                reconnect=reconnect,
            )
        elif vendor in GOOGLE_OAUTH_VENDORS:
            property_linked = complete_google_vendor_oauth_connection(
                client,
                org_id,
                connector_id,
                vendor,
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

    success_params: dict[str, str] = {
        "oauth": "success",
        "provider": vendor,
        "connectorId": connector_id,
    }
    if vendor == "google_analytics" and not property_linked:
        success_params["selectProperty"] = "1"

    return RedirectResponse(
        _frontend_redirect(redirect_path, success_params),
        status_code=302,
    )
