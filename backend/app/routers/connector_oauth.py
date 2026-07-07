"""Connector OAuth start/callback routes (STA-13)."""
from __future__ import annotations

import logging
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
from app.public_urls import PRODUCTION_APP_URL, normalize_public_url
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
from app.connectors.netsuite_oauth import (
    complete_netsuite_oauth_connection,
    netsuite_authorize_url,
    netsuite_credentials,
    netsuite_oauth_configured,
    netsuite_redirect_uri,
    normalize_vendor as normalize_netsuite_vendor,
)
from app.connectors.confluence_oauth import (
    complete_confluence_oauth_connection,
    confluence_authorize_url,
    confluence_credentials,
    confluence_oauth_configured,
    confluence_redirect_uri,
    normalize_vendor as normalize_confluence_vendor,
)
from app.connectors.workday_oauth import (
    complete_workday_oauth_connection,
    persist_workday_tenant_config,
    workday_oauth_configured,
    workday_redirect_uri,
    normalize_vendor as normalize_workday_vendor,
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
from app.connectors.marketo_oauth import (
    complete_marketo_client_credentials_connection,
    get_connector_munchkin_id,
    marketo_oauth_configured,
    normalize_vendor as normalize_marketo_vendor,
)
from app.services.marketo_workflow_service import on_marketo_org_ready
from app.connectors.pagerduty_webhooks import pagerduty_inbound_webhook_url
from app.connectors.salesforce_oauth import (
    complete_salesforce_oauth_connection,
    salesforce_authorize_url,
    salesforce_credentials,
    salesforce_oauth_configured,
    salesforce_redirect_uri,
    normalize_vendor as normalize_salesforce_vendor,
)
from app.connectors.slack_oauth import (
    complete_slack_oauth_connection,
    slack_authorize_url,
    slack_credentials,
    slack_oauth_configured,
    slack_redirect_uri,
    normalize_vendor as normalize_slack_vendor,
)
from app.connectors.google_vendor_oauth import (
    GOOGLE_OAUTH_VENDORS,
    complete_google_vendor_oauth_connection,
    google_oauth_configured,
    google_vendor_authorize_url,
    google_vendor_redirect_uri,
    normalize_google_vendor,
)
from app.connectors.google_oauth_common import google_oauth_credentials
from app.connectors.generic_oauth import (
    complete_generic_oauth_connection,
    generic_authorize_url,
    generic_credentials,
    generic_oauth_configured,
    generic_redirect_uri,
    persist_generic_oauth_connector_config,
    validate_generic_oauth_prerequisites,
)
from app.connectors.oauth_pkce import (
    DEDICATED_PKCE_OAUTH_VENDORS,
    code_challenge_s256,
    generate_code_verifier,
)
from app.connectors.oauth_provider_registry import (
    GENERIC_OAUTH_VENDORS,
    OAUTH_PROVIDER_REGISTRY,
    PARTNER_GATED_OAUTH_VENDORS,
    normalize_generic_vendor,
)
from app.connectors.oauth_state import (
    new_oauth_state_jti,
    new_oauth_state_nonce,
    sign_oauth_state,
    verify_oauth_state,
)
from app.connectors.platform import (
    is_connector_type_schema_error,
    mark_connector_pending_oauth,
    prepare_oauth_connector,
    raise_connector_type_schema_error,
)
from app.core.errors import error_detail
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/connectors/oauth", tags=["connector-oauth"])
logger = logging.getLogger(__name__)

SUPPORTED_OAUTH_PROVIDERS = frozenset(
    {
        "hubspot",
        "salesforce",
        "quickbooks",
        "netsuite",
        "jira",
        "confluence",
        "pagerduty",
        "notion",
        "slack",
        "workday",
        "marketo",
    }
) | GOOGLE_OAUTH_VENDORS | GENERIC_OAUTH_VENDORS


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
    if normalize_netsuite_vendor(provider) == "netsuite":
        return "netsuite"
    if normalize_jira_vendor(provider) == "jira":
        return "jira"
    if normalize_confluence_vendor(provider) == "confluence":
        return "confluence"
    if normalize_pagerduty_vendor(provider) == "pagerduty":
        return "pagerduty"
    if normalize_notion_vendor(provider) == "notion":
        return "notion"
    if normalize_slack_vendor(provider) == "slack":
        return "slack"
    if normalize_workday_vendor(provider) == "workday":
        return "workday"
    if normalize_marketo_vendor(provider) == "marketo":
        return "marketo"
    generic = normalize_generic_vendor(provider)
    if generic:
        return generic
    return vendor


class OAuthStartRequest(BaseModel):
    name: str = Field(..., min_length=1)
    connector_id: str | None = Field(default=None, alias="connectorId")
    redirect_path: str | None = Field(default="/connectors", alias="redirectPath")
    tenant_url: str | None = Field(default=None, alias="tenantUrl")
    tenant: str | None = None
    munchkin_id: str | None = Field(default=None, alias="munchkinId")
    subdomain: str | None = None
    instance_url: str | None = Field(default=None, alias="instanceUrl")
    owner: str | None = None
    repo: str | None = None

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
    base = normalize_public_url(settings.public_app_url, fallback=PRODUCTION_APP_URL).rstrip("/")
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
    elif vendor == "netsuite":
        configured = netsuite_oauth_configured(settings, environment_name)
        redirect_uri = netsuite_redirect_uri(settings)
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
    elif vendor == "slack":
        configured = slack_oauth_configured(settings, environment_name)
        redirect_uri = slack_redirect_uri(settings)
    elif vendor == "workday":
        configured = workday_oauth_configured(settings, environment_name)
        redirect_uri = workday_redirect_uri(settings)
    elif vendor == "marketo":
        configured = marketo_oauth_configured(settings, environment_name)
        redirect_uri = None
    elif vendor in GENERIC_OAUTH_VENDORS:
        configured = generic_oauth_configured(settings, vendor, environment_name)
        redirect_uri = generic_redirect_uri(settings, vendor)

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

    if vendor in PARTNER_GATED_OAUTH_VENDORS:
        label = vendor.replace("_", " ").title()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail(
                f"{label} requires partner approval before OAuth connect",
                "OAUTH_PARTNER_GATED",
            ),
        )

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
    if vendor == "netsuite" and not netsuite_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("NetSuite OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
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
    if vendor == "slack" and not slack_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Slack OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor == "workday" and not workday_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Workday OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor == "workday" and (not body.tenant_url or not body.tenant):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("Workday tenantUrl and tenant are required", "WORKDAY_TENANT_REQUIRED"),
        )
    if vendor in GOOGLE_OAUTH_VENDORS and not google_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Google OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor == "marketo" and not marketo_oauth_configured(settings, environment_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Marketo OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor in GENERIC_OAUTH_VENDORS and not generic_oauth_configured(settings, vendor, environment_name):
        label = vendor.replace("_", " ").title()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail(f"{label} OAuth is not configured", "OAUTH_NOT_CONFIGURED"),
        )
    if vendor in GENERIC_OAUTH_VENDORS:
        try:
            validate_generic_oauth_prerequisites(
                OAUTH_PROVIDER_REGISTRY[vendor],
                subdomain=body.subdomain,
                instance_url=body.instance_url,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail(str(exc), "OAUTH_PREREQUISITE_REQUIRED"),
            ) from exc

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
        stored_vendor = _resolve_oauth_vendor(str(row.get("vendor") or row.get("type") or ""))
        if stored_vendor != vendor:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connector vendor mismatch")
        mark_connector_pending_oauth(
            client,
            org_id=org_id,
            connector_id=str(connector_id),
            vendor=vendor,
            environment_name=environment_name,
        )
    else:
        try:
            connector_id, oauth_reconnect, is_new = prepare_oauth_connector(
                client,
                org_id=org_id,
                vendor=vendor,
                name=body.name,
                environment_name=environment_name,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            if is_connector_type_schema_error(exc):
                raise_connector_type_schema_error(exc)
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

    if vendor in GENERIC_OAUTH_VENDORS and (
        body.subdomain or body.instance_url or body.owner or body.repo
    ):
        persist_generic_oauth_connector_config(
            client,
            org_id,
            str(connector_id),
            vendor=vendor,
            subdomain=body.subdomain,
            instance_url=body.instance_url,
            owner=body.owner,
            repo=body.repo,
        )

    now = time.time()
    pkce_verifier: str | None = None
    pkce_challenge: str | None = None
    needs_pkce = vendor in DEDICATED_PKCE_OAUTH_VENDORS or (
        vendor in GENERIC_OAUTH_VENDORS and OAUTH_PROVIDER_REGISTRY[vendor].requires_pkce
    )
    if needs_pkce:
        pkce_verifier = generate_code_verifier()
        pkce_challenge = code_challenge_s256(pkce_verifier)

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
            "jti": new_oauth_state_jti(),
            "nonce": new_oauth_state_nonce(),
            "pkce_verifier": pkce_verifier,
        },
        _oauth_state_secret(settings),
    )

    auth_url = ""
    if vendor == "marketo":
        munchkin_id = (body.munchkin_id or "").strip()
        if not munchkin_id and connector_id:
            existing_cfg = (
                client.table("connectors")
                .select("config")
                .eq("id", connector_id)
                .eq("org_id", org_id)
                .limit(1)
                .execute()
            )
            if existing_cfg.data:
                munchkin_id = get_connector_munchkin_id(dict(existing_cfg.data[0])) or ""
        if not munchkin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail("munchkin_id is required for Marketo", "MARKETO_MUNCHKIN_REQUIRED"),
            )
        try:
            complete_marketo_client_credentials_connection(
                client,
                org_id,
                connector_id,
                settings,
                munchkin_id=munchkin_id,
                environment_name=environment_name,
                reconnect=reconnect,
            )
            on_marketo_org_ready(client, org_id, settings)
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_detail(f"Marketo token exchange failed: {exc}", "MARKETO_TOKEN_FAILED"),
            ) from exc
        auth_url = _frontend_redirect(
            settings,
            body.redirect_path or "/connectors",
            {
                "oauth": "success",
                "provider": vendor,
                "connectorId": connector_id,
            },
        )
    elif vendor == "hubspot":
        redirect_uri = hubspot_redirect_uri(settings)
        client_id, _secret = hubspot_credentials(settings, environment_name)
        auth_url = hubspot_authorize_url(client_id, redirect_uri, state)
    elif vendor == "salesforce":
        redirect_uri = salesforce_redirect_uri(settings)
        client_id, _secret = salesforce_credentials(settings, environment_name)
        auth_url = salesforce_authorize_url(
            client_id,
            redirect_uri,
            state,
            environment_name=environment_name,
            code_challenge=pkce_challenge,
        )
    elif vendor == "quickbooks":
        redirect_uri = quickbooks_redirect_uri(settings)
        client_id, _secret = quickbooks_credentials(settings, environment_name)
        auth_url = quickbooks_authorize_url(
            client_id, redirect_uri, state, environment_name=environment_name
        )
    elif vendor == "netsuite":
        redirect_uri = netsuite_redirect_uri(settings)
        client_id, _secret = netsuite_credentials(settings, environment_name)
        connector_row = (
            client.table("connectors")
            .select("config")
            .eq("org_id", org_id)
            .eq("id", connector_id)
            .limit(1)
            .execute()
        )
        connector_config = dict((connector_row.data or [{}])[0].get("config") or {})
        account_id = (connector_config.get("account_id") or connector_config.get("accountId") or "").strip()
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail(
                    "NetSuite account_id is required in connector config before OAuth",
                    "NETSUITE_ACCOUNT_ID_REQUIRED",
                ),
            )
        auth_url = netsuite_authorize_url(
            client_id,
            redirect_uri,
            state,
            account_id=account_id,
            environment_name=environment_name,
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
    elif vendor == "slack":
        redirect_uri = slack_redirect_uri(settings)
        client_id, _secret = slack_credentials(settings, environment_name)
        auth_url = slack_authorize_url(client_id, redirect_uri, state)
    elif vendor == "workday":
        persist_workday_tenant_config(
            client,
            org_id,
            str(connector_id),
            tenant_url=str(body.tenant_url or ""),
            tenant=str(body.tenant or ""),
        )
        try:
            complete_workday_oauth_connection(
                client,
                org_id,
                str(connector_id),
                None,
                settings,
                tenant_url=str(body.tenant_url or ""),
                tenant=str(body.tenant or ""),
                environment_name=environment_name,
                reconnect=reconnect,
                use_client_credentials=True,
            )
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_detail(f"Workday token exchange failed: {exc}", "WORKDAY_TOKEN_EXCHANGE_FAILED"),
            ) from exc
        auth_url = _frontend_redirect(
            settings,
            body.redirect_path or "/connectors",
            {
                "oauth": "success",
                "provider": vendor,
                "connectorId": str(connector_id),
            },
        )
    elif vendor in GOOGLE_OAUTH_VENDORS:
        redirect_uri = google_vendor_redirect_uri(settings, vendor)
        client_id, _secret = google_oauth_credentials(settings, environment_name)
        auth_url = google_vendor_authorize_url(vendor, client_id, redirect_uri, state)
    elif vendor in GENERIC_OAUTH_VENDORS:
        spec = OAUTH_PROVIDER_REGISTRY[vendor]
        redirect_uri = generic_redirect_uri(settings, vendor)
        client_id, _secret = generic_credentials(settings, vendor)
        ctx_subdomain = (body.subdomain or "").strip()
        ctx_instance = (body.instance_url or "").strip()
        if not ctx_subdomain or not ctx_instance:
            connector_row = (
                client.table("connectors")
                .select("config")
                .eq("org_id", org_id)
                .eq("id", connector_id)
                .limit(1)
                .execute()
            )
            connector_config = dict((connector_row.data or [{}])[0].get("config") or {})
            if not ctx_subdomain:
                ctx_subdomain = str(connector_config.get("subdomain") or "").strip()
            if not ctx_instance:
                ctx_instance = str(connector_config.get("instance_url") or "").strip()
        auth_url = generic_authorize_url(
            spec,
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            subdomain=ctx_subdomain,
            instance_url=ctx_instance,
            code_challenge=pkce_challenge,
        )
        if spec.requires_pkce:
            logger.info(
                "generic_oauth_authorize vendor=%s connector_id=%s redirect_uri=%s pkce=1 challenge_len=%s",
                vendor,
                connector_id,
                redirect_uri,
                len(pkce_challenge or ""),
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
    realm_id: str | None = Query(default=None, alias="realmId"),
    account_id: str | None = Query(default=None, alias="accountId"),
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
        payload = verify_oauth_state(
            state,
            _oauth_state_secret(settings),
            expected_provider=vendor,
        )
    except ValueError as exc:
        return RedirectResponse(
            _frontend_redirect(settings, "/connectors", {"oauth": "error", "message": str(exc)}),
            status_code=302,
        )

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
                code_verifier=str(payload.get("pkce_verifier") or "") or None,
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
        elif vendor == "netsuite":
            complete_netsuite_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                account_id=account_id,
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
        elif vendor == "slack":
            complete_slack_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                environment_name=environment_name,
                reconnect=reconnect,
            )
        elif vendor == "workday":
            complete_workday_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                environment_name=environment_name,
                reconnect=reconnect,
                use_client_credentials=not bool(code),
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
        elif vendor in GENERIC_OAUTH_VENDORS:
            complete_generic_oauth_connection(
                client,
                org_id,
                connector_id,
                code,
                settings,
                vendor=vendor,
                environment_name=environment_name,
                reconnect=reconnect,
                code_verifier=str(payload.get("pkce_verifier") or "") or None,
                user_id=str(payload.get("user_id") or "") or None,
            )
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "oauth_callback_failed vendor=%s connector_id=%s org_id=%s error=%s",
            vendor,
            connector_id,
            org_id,
            str(exc)[:200],
        )
        return RedirectResponse(
            _frontend_redirect(
                settings,
                redirect_path,
                {
                    "oauth": "error",
                    "provider": vendor,
                    "message": str(exc)[:200] or "token_exchange_failed",
                },
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
        _frontend_redirect(settings, redirect_path, success_params),
        status_code=302,
    )
