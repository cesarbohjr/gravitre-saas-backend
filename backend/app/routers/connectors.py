"""BE-30: Integration registry API. Admin-only. Never return secrets."""
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.repository import (
    create_connector,
    get_connector,
    get_decrypted_secret,
    list_connectors,
    set_secret,
    update_connector,
)
from app.core.crypto import decrypt_value, encrypt_value
from app.core.errors import error_detail
from app.billing.service import ADVANCED_CONNECTORS, get_plan_for_org, require_feature
from app.middleware.entitlements import resolve_entitlements
from app.connectors.connection_health import map_auth_status_to_connector_status, resolve_connector_auth_status
from app.connectors.platform import (
    is_connector_type_schema_error,
    masked_api_key_for_response,
    raise_connector_type_schema_error,
    store_connector_api_key,
)
from app.services.partner_marketplace_service import is_published_partner_vendor
from app.connectors.hubspot_oauth import ensure_hubspot_access_token, normalize_vendor
from app.connectors.salesforce_oauth import ensure_salesforce_access_token, normalize_vendor as normalize_salesforce_vendor
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
connectors_router = APIRouter(prefix="/api/connectors", tags=["connectors"])

INTEGRATION_TYPES = frozenset(
    {
        "slack",
        "email",
        "webhook",
        "salesforce",
        "hubspot",
        "postgresql",
        "microsoft_365",
        "excel",
        "custom",
    }
)


class CreateIntegrationRequest(BaseModel):
    type: str = Field(
        ...,
        pattern="^(slack|email|webhook|salesforce|hubspot|postgresql|microsoft_365|excel|custom)$",
    )
    config: dict = Field(default_factory=dict)


class UpdateIntegrationRequest(BaseModel):
    config: dict | None = None
    status: str | None = Field(None, pattern="^(active|inactive|error)$")


class SetSecretRequest(BaseModel):
    key_name: str = Field(..., min_length=1, max_length=64)
    value: str = Field(..., min_length=1)


TOOL_CONNECTOR_VENDORS = frozenset(
    {
        "zendesk",
        "github",
        "google_calendar",
        "fhir",
        "clio",
        "pipedrive",
    }
)

ALLOWED_CONNECTOR_VENDORS = frozenset(
    {
        "salesforce",
        "hubspot",
        "quickbooks",
        "netsuite",
        "workday",
        "marketo",
        "segment",
        "linkedin",
        "jira",
        "confluence",
        "pagerduty",
        "notion",
        "google_analytics",
        "gmail",
        "google_drive",
        "google_docs",
        "google_sheets",
        "google_calendar",
        "slack",
        "postgresql",
        "stripe",
        "microsoft365",
        "microsoft_teams",
        "outlook",
        "zendesk",
        "github",
        "email",
        "mailchimp",
        "mixpanel",
        "xero",
        "plaid",
        "twilio",
        "sendgrid",
        "airtable",
        "asana",
        "monday",
        "clickup",
        "zapier",
        "intercom",
        "freshdesk",
        "gorgias",
        "bamboohr",
        "gusto",
        "adp",
        "aws_s3",
        "mongodb",
        "snowflake",
        "motion",
        "constant_contact",
        "hootsuite",
        "n8n",
        "claude",
        "semrush",
        "stackadapt",
        "odoo",
        "absorb_lms",
        "canva",
        "figma",
        "apollo",
        "clay",
        "fhir",
        "clio",
        "pipedrive",
        # Phase 1 intelligence / category sources
        "fred",
        "sec_edgar",
        "world_bank",
        "oecd",
        "opencorporates",
        "nvd",
        "cisa_kev",
        "zoominfo",
        "linkedin_sales_navigator",
        "crunchbase",
        "pdl",
    }
)


class ConnectorCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    vendor: str = Field(..., min_length=1)
    description: str | None = None
    api_key: str | None = Field(default=None, alias="apiKey")
    webhook_url: str | None = Field(default=None, alias="webhookUrl")
    sync_frequency: str | None = Field(default=None, alias="syncFrequency")
    environment_id: str | None = Field(default=None, alias="environmentId")
    config: dict | None = None
    secrets: dict[str, str] | None = None

    model_config = {"populate_by_name": True}


class ConnectorUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    api_key: str | None = Field(default=None, alias="apiKey")
    webhook_url: str | None = Field(default=None, alias="webhookUrl")
    sync_frequency: str | None = Field(default=None, alias="syncFrequency")
    status: str | None = None
    config: dict | None = None
    phi_capable: bool | None = Field(default=None, alias="phiCapable")

    model_config = {"populate_by_name": True}


class ConnectorDeleteRequest(BaseModel):
    confirm_name: str = Field(..., alias="confirmName")

    model_config = {"populate_by_name": True}


class ConnectorSyncRequest(BaseModel):
    full_sync: bool | None = Field(default=None, alias="fullSync")


def _docs_url(vendor: str) -> str | None:
    mapping = {
        "salesforce": "https://developer.salesforce.com/docs",
        "hubspot": "https://developers.hubspot.com/docs",
        "pipedrive": "https://developers.pipedrive.com/docs/api/v1",
        "slack": "https://api.slack.com/docs",
        "postgresql": "https://www.postgresql.org/docs/",
        "stripe": "https://stripe.com/docs/api",
        "microsoft365": "https://docs.microsoft.com/en-us/graph/",
        "quickbooks": "https://developer.intuit.com/app/developer/qbo/docs",
        "jira": "https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/",
        "confluence": "https://developer.atlassian.com/cloud/confluence/rest/v2/intro/",
        "pagerduty": "https://developer.pagerduty.com/docs/",
        "notion": "https://developers.notion.com/docs",
        "google_analytics": "https://developers.google.com/analytics/devguides/config/admin/v1",
        "google_calendar": "https://developers.google.com/calendar/api/guides/overview",
        "gmail": "https://developers.google.com/gmail/api",
        "google_drive": "https://developers.google.com/drive/api",
        "google_docs": "https://developers.google.com/docs/api",
        "google_sheets": "https://developers.google.com/sheets/api",
        "apollo": "https://docs.apollo.io/docs/use-oauth-20-authorization-flow-to-access-apollo-user-information-partners",
        "clay": "https://university.clay.com/docs/using-clay-as-an-api",
    }
    return mapping.get(vendor)


def _connector_response_item(
    row: dict,
    *,
    environment_name: str,
    settings: Settings,
    client,
    org_id: str,
    force_live: bool = False,
) -> dict:
    from app.connectors.connector_availability_service import evaluate_connector_availability

    connector_id = str(row["id"])
    vendor = row.get("vendor") or row.get("type") or ""
    availability = evaluate_connector_availability(
        client,
        org_id,
        row,
        settings,
        environment_name=str(row.get("environment") or environment_name),
        force_live=force_live,
    )
    api_key = masked_api_key_for_response(client, connector_id, row, settings)
    return {
        "id": connector_id,
        "name": row.get("name") or "",
        "vendor": vendor,
        "description": row.get("description"),
        "status": availability.get("health_status") or row.get("status") or "healthy",
        "authStatus": availability.get("auth_status"),
        "displayStatus": availability.get("display_status"),
        "environment": row.get("environment") or environment_name,
        "lastSync": row.get("last_sync_at"),
        "recordsSynced": row.get("records_synced") or 0,
        "syncFrequency": row.get("sync_frequency") or "1h",
        "availability": {
            "configured": availability.get("configured"),
            "authenticated": availability.get("authenticated"),
            "tokenValid": availability.get("token_valid"),
            "scopesValid": availability.get("scopes_valid"),
            "healthy": availability.get("display_status") in {"connected", "syncing"},
            "executable": availability.get("execution_available"),
            "blockingReason": availability.get("blocking_reason"),
            "recoveryAction": availability.get("recovery_action"),
            "lastCheckedAt": availability.get("last_checked_at"),
            "sourceOfTruth": availability.get("source_of_truth"),
        },
        "config": {
            "apiKey": api_key,
            "webhookUrl": row.get("webhook_url"),
            "authType": (row.get("config") or {}).get("auth_type"),
        },
        "docsUrl": row.get("docs_url"),
        "phiCapable": bool(row.get("phi_capable")),
    }


def _validate_webhook(url: str | None) -> None:
    if not url:
        return
    if not url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("webhookUrl must be HTTPS", "INVALID_CONFIG"),
        )


@router.get("")
async def list_integrations_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """List integrations. No secrets ever."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    items = list_connectors(client, org_id, environment_name=environment_name)
    return {
        "integrations": [
            {
                "id": str(c["id"]),
                "type": c["type"],
                "status": c["status"],
                "config": c.get("config", {}),
                "environment": c.get("environment", environment_name),
                "updated_at": c.get("updated_at"),
            }
            for c in items
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_integration_route(
    body: CreateIntegrationRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Create integration. Config only; add secrets via POST /:id/secrets."""
    _user, org_id = _admin
    service_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    entitlements = resolve_entitlements(settings, org_id)
    connector_limit = (entitlements.get("limits") or {}).get("connectors")
    if connector_limit is not None:
        connector_count_resp = (
            service_client.table("connectors")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .is_("deleted_at", "null")
            .execute()
        )
        connector_count = (
            connector_count_resp.count
            if hasattr(connector_count_resp, "count") and connector_count_resp.count is not None
            else len(connector_count_resp.data or [])
        )
        if connector_count >= int(connector_limit):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connector limit reached for {entitlements.get('tier', 'current')} tier",
            )
    plan = get_plan_for_org(service_client, org_id)
    normalized = (body.type or "").strip().lower()
    vendor_key = "microsoft365" if normalized == "microsoft_365" else normalized
    if vendor_key in ADVANCED_CONNECTORS:
        require_feature(plan, "advanced_connectors")
    client = service_client
    conn = create_connector(client, org_id, body.type, body.config, _user["user_id"], environment_name=environment_name)
    return {
        "id": str(conn["id"]),
        "type": conn["type"],
        "status": conn["status"],
        "config": conn.get("config", {}),
        "environment": conn.get("environment", environment_name),
        "updated_at": conn.get("updated_at"),
    }


@router.get("/{integration_id}")
async def get_integration_route(
    integration_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Get integration. No secrets."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    conn = get_connector(client, org_id, str(integration_id), environment_name=environment_name)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return {
        "id": str(conn["id"]),
        "type": conn["type"],
        "status": conn["status"],
        "config": conn.get("config", {}),
        "environment": conn.get("environment", environment_name),
        "updated_at": conn.get("updated_at"),
    }


@router.patch("/{integration_id}")
async def update_integration_route(
    integration_id: UUID,
    body: UpdateIntegrationRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Update integration config/status."""
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    conn = update_connector(client, org_id, str(integration_id), body.config, body.status, environment_name=environment_name)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return {
        "id": str(conn["id"]),
        "type": conn["type"],
        "status": conn["status"],
        "config": conn.get("config", {}),
        "environment": conn.get("environment", environment_name),
        "updated_at": conn.get("updated_at"),
    }


@router.post("/{integration_id}/secrets")
async def set_connector_secret(
    integration_id: UUID,
    body: SetSecretRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Set a secret. Never returned. Requires CONNECTOR_SECRETS_ENCRYPTION_KEY."""
    _user, org_id = _admin
    if not settings.connector_secrets_encryption_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Secrets encryption not configured",
        )
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    conn = get_connector(client, org_id, str(integration_id), environment_name=environment_name)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    set_secret(client, org_id, str(integration_id), body.key_name, body.value, settings)
    return {"key_name": body.key_name, "message": "Secret stored"}


@router.post("/{integration_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_integration_route(
    integration_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Request a manual sync for an integration."""
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    conn = get_connector(client, org_id, str(integration_id), environment_name=environment_name)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="integration.sync.requested",
        resource_type="integration",
        resource_id=str(integration_id),
        metadata={"environment": environment_name},
    )
    return {"id": str(conn["id"]), "status": conn.get("status") or "active", "message": "Sync requested"}


@connectors_router.get("")
async def list_connectors_route_alias(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    live: bool = Query(default=False, description="Refresh OAuth token validity before responding"),
) -> dict:
    """List connectors (spec shape)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    q = (
        client.table("connectors")
        .select(
            "id, name, vendor, description, status, environment, config, sync_frequency, "
            "last_sync_at, records_synced, docs_url, api_key_encrypted, webhook_url"
        )
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .is_("deleted_at", "null")
        .order("updated_at", desc=True)
        .execute()
    )
    items = [
        _connector_response_item(
            row,
            environment_name=environment_name,
            settings=settings,
            client=client,
            org_id=org_id,
            force_live=live,
        )
        for row in list(q.data or [])
    ]
    return {"connectors": items}


@connectors_router.get("/catalog/simulation-coverage")
async def list_connector_simulation_coverage(
    _user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Per-vendor demo-safe simulation coverage (STA-285). Zero coverage = demo-blocked."""
    from app.connectors.simulation_coverage import build_simulation_coverage_report

    return build_simulation_coverage_report()


@connectors_router.get("/catalog/actions")
async def list_connector_action_catalog(
    _user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Full v1/v2/v3 action catalog and demo workflows for all connectors."""
    from app.connectors.action_catalog import list_full_catalog

    return list_full_catalog()


@connectors_router.get("/catalog/execution-matrix")
async def list_connector_execution_matrix(
    _user: Annotated[dict, Depends(get_current_user)],
    vendor: str | None = None,
) -> dict:
    """Inspectable connector action execution matrix for chat and invoke_tool coverage."""
    from app.services.connector_execution_matrix import (
        get_execution_matrix,
        matrix_summary,
    )

    entries = get_execution_matrix()
    if vendor:
        entries = [row for row in entries if row.get("connectorId") == vendor.lower().strip()]
    return {"summary": matrix_summary(), "entries": entries}


@connectors_router.get("/catalog/actions/{vendor}")
async def get_connector_action_catalog_vendor(
    vendor: str,
    _user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Per-vendor v1 read, v2 write, v3 advanced tools and demo workflows."""
    from app.connectors.action_catalog import get_vendor_catalog_dict

    payload = get_vendor_catalog_dict(vendor)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown vendor")
    return payload


@connectors_router.get("/{connector_id}")
async def get_connector_route_alias(
    connector_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Get connector (spec shape)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        client.table("connectors")
        .select(
            "id, name, vendor, description, status, environment, config, sync_frequency, "
            "last_sync_at, records_synced, docs_url, api_key_encrypted, webhook_url"
        )
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(connector_id))
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    data = row.data[0]
    return {
        "connector": _connector_response_item(
            data,
            environment_name=environment_name,
            settings=settings,
            client=client,
            org_id=org_id,
        )
    }


@connectors_router.post("/{connector_id}/test")
async def test_connector_route(
    connector_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Test connector connectivity (OAuth token validity for HubSpot)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        client.table("connectors")
        .select("id, vendor, name, environment")
        .eq("org_id", org_id)
        .eq("id", str(connector_id))
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    data = row.data[0]
    vendor = normalize_vendor(data.get("vendor") or "")
    connector_env = data.get("environment") or environment_name
    if vendor == "hubspot":
        token, err = ensure_hubspot_access_token(
            client,
            org_id,
            str(connector_id),
            settings,
            environment_name=connector_env,
        )
        if token:
            return {"success": True, "message": "HubSpot connection is valid"}
        return {"success": False, "message": err or "HubSpot connection failed"}
    if normalize_salesforce_vendor(vendor) == "salesforce":
        token, err = ensure_salesforce_access_token(
            client,
            org_id,
            str(connector_id),
            settings,
            environment_name=connector_env,
        )
        if token:
            return {"success": True, "message": "Salesforce connection is valid"}
        return {"success": False, "message": err or "Salesforce connection failed"}
    if vendor == "pipedrive":
        from app.services.pipedrive_tools import verify_pipedrive_connection

        ok, msg = verify_pipedrive_connection(
            client,
            org_id,
            str(connector_id),
            settings,
            environment_name=connector_env,
        )
        return {"success": ok, "message": msg}
    if vendor in TOOL_CONNECTOR_VENDORS:
        conn = get_connector(client, org_id, str(connector_id), environment_name=environment_name)
        if not conn:
            return {"success": False, "message": "Connector not found"}
        if vendor == "zendesk":
            from app.connectors.connector_tool_auth import resolve_zendesk_auth

            cfg = conn.get("config") or {}
            if not cfg.get("subdomain") and not cfg.get("zendesk_subdomain"):
                return {"success": False, "message": "Missing subdomain in config"}
            try:
                _sub, _email, api_tok, oauth_tok = resolve_zendesk_auth(
                    client, org_id, conn, settings, environment_name=environment_name
                )
            except ValueError as exc:
                return {"success": False, "message": str(exc)}
            if not oauth_tok and not (api_tok):
                return {"success": False, "message": "Missing Zendesk OAuth or api_token credentials"}
        if vendor == "github":
            from app.connectors.connector_tool_auth import resolve_github_access_token

            token = resolve_github_access_token(
                client, org_id, str(connector_id), settings, environment_name=environment_name
            )
            if not token:
                return {"success": False, "message": "Missing GitHub OAuth or PAT"}
        if vendor in {"google_calendar", "gmail", "google_drive", "google_docs", "google_sheets", "google_analytics"}:
            from app.connectors.google_vendor_oauth import ensure_google_vendor_session

            token, err = ensure_google_vendor_session(
                client, org_id, str(connector_id), settings, environment_name=environment_name
            )
            if token:
                return {"success": True, "message": f"{vendor} connection is valid"}
            if vendor == "google_calendar":
                legacy = get_decrypted_secret(client, str(connector_id), "access_token", settings)
                if legacy:
                    return {"success": True, "message": "Google Calendar access_token configured (legacy)"}
            return {"success": False, "message": err or f"{vendor} not connected"}
        return {"success": True, "message": f"{vendor} credentials configured"}
    return {"success": True, "message": "No automated test for this connector type"}


@connectors_router.post("/{connector_id}/secrets")
async def set_connector_secret_alias(
    connector_id: UUID,
    body: SetSecretRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Set encrypted connector secret (alias of integrations secrets route)."""
    return await set_connector_secret(connector_id, body, _admin, environment_name, settings)


@connectors_router.post("/{connector_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_connector_route_alias(
    connector_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: ConnectorSyncRequest | None = None,
) -> dict:
    """Manual sync — runs knowledge sync for Notion; legacy status for other connectors."""
    import asyncio

    from app.services.knowledge_sync_service import SOURCE_REGISTRY, trigger_connector_knowledge_sync

    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    conn = (
        client.table("connectors")
        .select("id, status, name, vendor, type")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(connector_id))
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not conn.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    row = conn.data[0]
    vendor = str(row.get("type") or row.get("vendor") or "").lower()
    if vendor in SOURCE_REGISTRY:
        full_sync = bool((body or ConnectorSyncRequest()).full_sync)
        try:
            result = await asyncio.to_thread(
                trigger_connector_knowledge_sync,
                client,
                settings,
                org_id,
                str(connector_id),
                actor_id=str(_user["user_id"]),
                trigger_type="manual",
                full_sync=full_sync,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            # Surface PostgREST/schema errors (e.g. missing rag_sources.created_by) instead of opaque 500.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_detail(str(exc)[:300] or "Knowledge sync failed", "KNOWLEDGE_SYNC_FAILED"),
            ) from exc
        return {
            "success": True,
            "status": "completed",
            "syncId": f"knowledge-{str(connector_id)[:8]}",
            **result,
        }

    status_value = row.get("status")
    if status_value == "syncing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_detail("Sync already in progress", "SYNC_IN_PROGRESS"),
        )
    sync_id = f"sync-{str(connector_id)[:8]}-{_user['user_id'][:6]}"
    client.table("connectors").update(
        {"status": "syncing", "last_sync_id": sync_id, "last_sync_at": None}
    ).eq("id", str(connector_id)).eq("org_id", org_id).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="connector.sync.manual",
        resource_type="connector",
        resource_id=str(connector_id),
        metadata={"environment": environment_name},
    )
    return {"success": True, "syncId": sync_id, "status": "syncing"}


@connectors_router.post("", status_code=status.HTTP_201_CREATED)
async def create_connector_route(
    body: ConnectorCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    entitlements = resolve_entitlements(settings, org_id)
    connector_limit = (entitlements.get("limits") or {}).get("connectors")
    vendor = (body.vendor or "").strip().lower().replace(" ", "")
    if vendor == "googlecalendar":
        vendor = "google_calendar"
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    if vendor not in ALLOWED_CONNECTOR_VENDORS and not is_published_partner_vendor(client, vendor):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid vendor")
    if vendor == "snowflake":
        from app.connectors.snowflake_config import validate_snowflake_config

        sf_errors = validate_snowflake_config(body.config)
        if sf_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail("; ".join(sf_errors), "SNOWFLAKE_CONFIG_INVALID"),
            )
    plan = get_plan_for_org(client, org_id)
    if vendor in ADVANCED_CONNECTORS:
        require_feature(plan, "advanced_connectors")
    _validate_webhook(body.webhook_url)
    docs_url = _docs_url(vendor)
    if connector_limit is not None:
        connector_count_resp = (
            client.table("connectors")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .is_("deleted_at", "null")
            .execute()
        )
        connector_count = (
            connector_count_resp.count
            if hasattr(connector_count_resp, "count") and connector_count_resp.count is not None
            else len(connector_count_resp.data or [])
        )
        if connector_count >= int(connector_limit):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connector limit reached for {entitlements.get('tier', 'current')} tier",
            )
    plan = get_plan_for_org(client, org_id)
    features = plan.get("features") or {}
    if vendor in ADVANCED_CONNECTORS and not features.get("advanced_connectors"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Upgrade required", "UNAUTHORIZED", {"feature": "advanced_connectors"}),
        )
    connector_status = "active" if vendor in TOOL_CONNECTOR_VENDORS else "healthy"
    row = {
        "org_id": org_id,
        "name": body.name.strip(),
        "vendor": vendor,
        "type": vendor,
        "description": body.description,
        "status": connector_status,
        "environment": environment_name,
        "sync_frequency": body.sync_frequency or "1h",
        "webhook_url": body.webhook_url,
        "docs_url": docs_url,
        "config": body.config or {},
    }
    if vendor == "fhir":
        row["phi_capable"] = True
        row["config"] = {
            **(row["config"] or {}),
            "sandbox": bool((row["config"] or {}).get("sandbox", True)),
            "base_url": (row["config"] or {}).get("base_url")
            or (row["config"] or {}).get("baseUrl")
            or "https://hapi.fhir.org/baseR4",
        }
    if vendor == "odoo":
        cfg = dict(body.config or {})
        odoo_url = (
            cfg.get("odoo_url")
            or cfg.get("odooUrl")
            or cfg.get("instance_url")
            or cfg.get("instanceUrl")
            or ""
        )
        row["description"] = body.description or "Odoo (API key)"
        row["config"] = {
            **cfg,
            "auth_type": "api_key",
            "odoo_url": str(odoo_url).strip().rstrip("/"),
            "database": str(cfg.get("database") or cfg.get("db") or "").strip(),
        }
        row["docs_url"] = "https://www.odoo.com/documentation/17.0/developer/reference/external_api.html"
    if vendor == "clay":
        cfg = dict(body.config or {})
        webhook = str(body.webhook_url or cfg.get("webhook_url") or cfg.get("webhookUrl") or "").strip()
        row["description"] = body.description or "Clay enrichment and data workflows"
        clay_config: dict[str, Any] = {
            **cfg,
            "auth_type": "api_key",
            "webhook_url": webhook,
            "table_name": str(cfg.get("table_name") or cfg.get("tableName") or "").strip(),
            "workspace_id": str(cfg.get("workspace_id") or cfg.get("workspaceId") or "").strip(),
        }
        if isinstance(cfg.get("tables"), list):
            clay_config["tables"] = cfg["tables"]
        crm_target = str(cfg.get("crm_sync_target") or cfg.get("crmSyncTarget") or "").strip()
        crm_connector_id = str(cfg.get("crm_connector_id") or cfg.get("crmConnectorId") or "").strip()
        if crm_target:
            clay_config["crm_sync_target"] = crm_target
        if crm_connector_id:
            clay_config["crm_connector_id"] = crm_connector_id
        row["config"] = clay_config
        if webhook:
            row["webhook_url"] = webhook
    connector_id: str
    try:
        r = client.table("connectors").insert(row).execute()
        if not r.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Connector create failed")
        connector_id = str(r.data[0]["id"])
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "23505" not in msg and "connectors_org_name_key" not in msg:
            if is_connector_type_schema_error(exc):
                raise_connector_type_schema_error(exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail(f"Connector create failed: {exc}", "CONNECTOR_CREATE_FAILED"),
            ) from exc
        existing = (
            client.table("connectors")
            .select("id, vendor")
            .eq("org_id", org_id)
            .eq("name", body.name.strip())
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if not existing.data:
            soft_deleted = (
                client.table("connectors")
                .select("id")
                .eq("org_id", org_id)
                .eq("name", body.name.strip())
                .not_.is_("deleted_at", "null")
                .limit(1)
                .execute()
            )
            if soft_deleted.data:
                connector_id = str(soft_deleted.data[0]["id"])
                update_payload = {k: v for k, v in row.items() if k not in {"org_id", "name"}}
                update_payload["deleted_at"] = None
                client.table("connectors").update(update_payload).eq("id", connector_id).eq(
                    "org_id", org_id
                ).execute()
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=error_detail(
                        "Connector name already exists. Choose a different name.",
                        "CONNECTOR_NAME_CONFLICT",
                    ),
                ) from exc
        else:
            connector_id = str(existing.data[0]["id"])
            update_payload = {k: v for k, v in row.items() if k not in {"org_id", "name"}}
            client.table("connectors").update(update_payload).eq("id", connector_id).eq("org_id", org_id).execute()
    if body.api_key:
        api_key_plain = body.api_key.strip()
        encrypted = store_connector_api_key(client, org_id, connector_id, api_key_plain, settings)
        if encrypted:
            client.table("connectors").update({"api_key_encrypted": encrypted}).eq("id", connector_id).eq(
                "org_id", org_id
            ).execute()
        if vendor == "apollo" and settings.connector_secrets_encryption_key:
            set_secret(client, org_id, connector_id, "api_token", api_key_plain, settings)
    if body.secrets:
        if not settings.connector_secrets_encryption_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Secrets encryption not configured",
            )
        for key_name, value in body.secrets.items():
            if value:
                set_secret(client, org_id, connector_id, key_name, value, settings)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="connector.created",
        resource_type="connector",
        resource_id=connector_id,
        metadata={"environment": environment_name},
    )
    if is_published_partner_vendor(client, vendor):
        try:
            from app.services.marketplace_billing_service import record_marketplace_install

            record_marketplace_install(
                client,
                customer_org_id=org_id,
                connector_id=connector_id,
                vendor=vendor,
            )
        except Exception:
            pass
    return {"id": connector_id}


@connectors_router.patch("/{connector_id}")
async def update_connector_route(
    connector_id: UUID,
    body: ConnectorUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    _validate_webhook(body.webhook_url)
    payload: dict = {}
    if body.name is not None:
        payload["name"] = body.name
    if body.description is not None:
        payload["description"] = body.description
    if body.sync_frequency is not None:
        payload["sync_frequency"] = body.sync_frequency
    if body.status is not None:
        payload["status"] = body.status
    if body.phi_capable is not None:
        from app.services.hipaa_service import set_connector_phi_capable

        set_connector_phi_capable(
            client,
            org_id=org_id,
            connector_id=str(connector_id),
            phi_capable=body.phi_capable,
            actor_id=_user["user_id"],
        )
    if body.webhook_url is not None:
        payload["webhook_url"] = body.webhook_url
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    if body.config is not None:
        existing_row = (
            client.table("connectors")
            .select("config")
            .eq("org_id", org_id)
            .eq("id", str(connector_id))
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        current_config = {}
        if existing_row.data:
            current_config = existing_row.data[0].get("config") or {}
        payload["config"] = {**current_config, **body.config}
    api_key_plain = (body.api_key or "").strip() or None
    if api_key_plain:
        encrypted = store_connector_api_key(client, org_id, str(connector_id), api_key_plain, settings)
        if encrypted:
            payload["api_key_encrypted"] = encrypted
    if not payload and not api_key_plain:
        return await get_connector_route_alias(connector_id, _admin[0], org_id, environment_name, settings)
    if payload:
        updated = (
            client.table("connectors")
            .update(payload)
            .eq("org_id", org_id)
            .eq("id", str(connector_id))
            .is_("deleted_at", "null")
            .execute()
        )
        if not updated.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    else:
        exists = (
            client.table("connectors")
            .select("id")
            .eq("org_id", org_id)
            .eq("id", str(connector_id))
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if not exists.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="connector.config.updated",
        resource_type="connector",
        resource_id=str(connector_id),
        metadata={"environment": environment_name, "fields": list(payload.keys())},
    )
    return await get_connector_route_alias(connector_id, _admin[0], org_id, environment_name, settings)


async def _delete_connector_impl(
    connector_id: UUID,
    body: ConnectorDeleteRequest,
    _admin: tuple,
    settings: Settings,
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    existing = (
        client.table("connectors")
        .select("id, name, environment")
        .eq("org_id", org_id)
        .eq("id", str(connector_id))
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    row = existing.data[0]
    name = row.get("name") or ""
    if body.confirm_name.strip() != name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("Name mismatch", "NAME_MISMATCH"),
        )
    try:
        deps = (
            client.table("workflow_nodes")
            .select("id, workflow_id")
            .eq("org_id", org_id)
            .eq("connector_id", str(connector_id))
            .execute()
        )
        if deps.data:
            workflows = list({str(d.get("workflow_id")) for d in deps.data if d.get("workflow_id")})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail("Has dependencies", "HAS_DEPENDENCIES", {"workflows": workflows}),
            )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        # workflow_nodes may be absent in some environments; do not block connector removal.
        pass

    deleted_at = datetime.now(timezone.utc).isoformat()
    updated = (
        client.table("connectors")
        .update({"deleted_at": deleted_at})
        .eq("id", str(connector_id))
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="connector.deleted",
        resource_type="connector",
        resource_id=str(connector_id),
        metadata={"environment": row.get("environment")},
    )
    return {"success": True}


@connectors_router.delete("/{connector_id}")
async def delete_connector_route(
    connector_id: UUID,
    body: ConnectorDeleteRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await _delete_connector_impl(connector_id, body, _admin, settings)


@connectors_router.post("/{connector_id}/delete")
async def delete_connector_post_route(
    connector_id: UUID,
    body: ConnectorDeleteRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """POST alias for delete (avoids DELETE+body issues in some proxies)."""
    return await _delete_connector_impl(connector_id, body, _admin, settings)


@connectors_router.get("/{connector_id}/docs")
async def get_connector_docs(
    connector_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        client.table("connectors")
        .select("id, vendor, docs_url")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(connector_id))
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    vendor = row.data[0].get("vendor") or ""
    docs_url = row.data[0].get("docs_url") or _docs_url(vendor)
    return {"docsUrl": docs_url}
