"""BE-30: Integration registry API. Admin-only. Never return secrets."""
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.repository import (
    create_connector,
    get_connector,
    list_connectors,
    set_secret,
    update_connector,
)
from app.core.crypto import decrypt_value, encrypt_value, mask_value
from app.core.errors import error_detail
from app.billing.service import ADVANCED_CONNECTORS, get_plan_for_org, require_feature
from app.middleware.entitlements import resolve_entitlements
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


class ConnectorCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    vendor: str = Field(..., min_length=1)
    description: str | None = None
    api_key: str | None = Field(default=None, alias="apiKey")
    webhook_url: str | None = Field(default=None, alias="webhookUrl")
    sync_frequency: str | None = Field(default=None, alias="syncFrequency")
    environment_id: str | None = Field(default=None, alias="environmentId")


class ConnectorUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    api_key: str | None = Field(default=None, alias="apiKey")
    webhook_url: str | None = Field(default=None, alias="webhookUrl")
    sync_frequency: str | None = Field(default=None, alias="syncFrequency")
    status: str | None = None


class ConnectorDeleteRequest(BaseModel):
    confirm_name: str = Field(..., alias="confirmName")


class ConnectorSyncRequest(BaseModel):
    full_sync: bool | None = Field(default=None, alias="fullSync")


def _docs_url(vendor: str) -> str | None:
    mapping = {
        "salesforce": "https://developer.salesforce.com/docs",
        "hubspot": "https://developers.hubspot.com/docs",
        "slack": "https://api.slack.com/docs",
        "postgresql": "https://www.postgresql.org/docs/",
        "stripe": "https://stripe.com/docs/api",
        "microsoft365": "https://docs.microsoft.com/en-us/graph/",
    }
    return mapping.get(vendor)


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
    items = []
    for row in list(q.data or []):
        api_key = None
        if row.get("api_key_encrypted") and settings.encryption_key:
            try:
                api_key = decrypt_value(row["api_key_encrypted"], settings.encryption_key)
            except Exception:
                api_key = None
        items.append(
            {
                "id": str(row["id"]),
                "name": row.get("name") or "",
                "vendor": row.get("vendor") or row.get("type") or "",
                "description": row.get("description"),
                "status": row.get("status") or "healthy",
                "environment": row.get("environment") or environment_name,
                "lastSync": row.get("last_sync_at"),
                "recordsSynced": row.get("records_synced") or 0,
                "syncFrequency": row.get("sync_frequency") or "1h",
                "config": {
                    "apiKey": mask_value(api_key),
                    "webhookUrl": row.get("webhook_url"),
                },
                "docsUrl": row.get("docs_url"),
            }
        )
    return {"connectors": items}


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
    api_key = None
    if data.get("api_key_encrypted") and settings.encryption_key:
        try:
            api_key = decrypt_value(data["api_key_encrypted"], settings.encryption_key)
        except Exception:
            api_key = None
    return {
        "connector": {
            "id": str(data["id"]),
            "name": data.get("name") or "",
            "vendor": data.get("vendor") or data.get("type") or "",
            "description": data.get("description"),
            "status": data.get("status") or "healthy",
            "environment": data.get("environment") or environment_name,
            "lastSync": data.get("last_sync_at"),
            "recordsSynced": data.get("records_synced") or 0,
            "syncFrequency": data.get("sync_frequency") or "1h",
            "config": {
                "apiKey": mask_value(api_key),
                "webhookUrl": data.get("webhook_url"),
            },
            "docsUrl": data.get("docs_url"),
        }
    }


@connectors_router.post("/{connector_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_connector_route_alias(
    connector_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Manual sync request."""
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    conn = (
        client.table("connectors")
        .select("id, status, name, vendor")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(connector_id))
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not conn.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    status_value = conn.data[0].get("status")
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
    vendor = (body.vendor or "").strip().lower()
    if vendor not in {
        "salesforce",
        "hubspot",
        "slack",
        "postgresql",
        "stripe",
        "microsoft365",
    }:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid vendor")
    plan = get_plan_for_org(create_client(settings.supabase_url, settings.supabase_service_role_key), org_id)
    if vendor in ADVANCED_CONNECTORS:
        require_feature(plan, "advanced_connectors")
    _validate_webhook(body.webhook_url)
    api_key_encrypted = None
    if body.api_key:
        if not settings.encryption_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_detail("ENCRYPTION_KEY not configured", "INVALID_CONFIG"),
            )
        api_key_encrypted = encrypt_value(body.api_key, settings.encryption_key)
    docs_url = _docs_url(vendor)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
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
    row = {
        "org_id": org_id,
        "name": body.name.strip(),
        "vendor": vendor,
        "type": vendor,
        "description": body.description,
        "status": "healthy",
        "environment": environment_name,
        "sync_frequency": body.sync_frequency or "1h",
        "api_key_encrypted": api_key_encrypted,
        "webhook_url": body.webhook_url,
        "docs_url": docs_url,
        "config": {},
    }
    r = client.table("connectors").insert(row).execute()
    if not r.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Connector create failed")
    connector_id = str(r.data[0]["id"])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="connector.created",
        resource_type="connector",
        resource_id=connector_id,
        metadata={"environment": environment_name},
    )
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
    if body.webhook_url is not None:
        payload["webhook_url"] = body.webhook_url
    if body.api_key:
        if not settings.encryption_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_detail("ENCRYPTION_KEY not configured", "INVALID_CONFIG"),
            )
        payload["api_key_encrypted"] = encrypt_value(body.api_key, settings.encryption_key)
    if not payload:
        return await get_connector_route_alias(connector_id, _admin[0], org_id, environment_name, settings)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    updated = (
        client.table("connectors")
        .update(payload)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(connector_id))
        .is_("deleted_at", "null")
        .execute()
    )
    if not updated.data:
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


@connectors_router.delete("/{connector_id}")
async def delete_connector_route(
    connector_id: UUID,
    body: ConnectorDeleteRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    existing = (
        client.table("connectors")
        .select("id, name")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(connector_id))
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    name = existing.data[0].get("name") or ""
    if body.confirm_name.strip() != name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("Name mismatch", "NAME_MISMATCH"),
        )
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
    client.table("connectors").update(
        {"deleted_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", str(connector_id)).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="connector.deleted",
        resource_type="connector",
        resource_id=str(connector_id),
        metadata={"environment": environment_name},
    )
    return {"success": True}


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
