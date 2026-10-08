"""Managed-auth routes for Nango-backed long-tail connectors.

Nango is an implementation detail. Customer-facing responses use Gravitre connector
language and never expose provider credentials.
"""
from __future__ import annotations

from typing import Annotated
import hashlib
import hmac
import json
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from supabase import create_client
from app.core.db import shared_service_client

from app.auth.dependencies import get_environment_context, require_admin, require_org_member
from app.config import Settings, get_settings
from app.connectors.nango_client import create_connect_session, nango_configured
from app.connectors.nango_registry import get_nango_connector_spec, NANGO_CONNECTOR_REGISTRY
from app.connectors.platform import (
    is_connector_type_schema_error,
    raise_connector_type_schema_error,
)
from app.core.errors import error_detail
from app.core.safe_dict import safe_normalize_stored_dict
from app.workflows.audit import write_audit_event


router = APIRouter(prefix="/api/connectors/managed-auth", tags=["connector-managed-auth"])


def _verify_nango_webhook_signature(raw_body: bytes, signature: str | None, signing_key: str) -> bool:
    key = (signing_key or "").strip()
    supplied = (signature or "").strip().lower()
    if not key or not supplied:
        return False
    expected = hmac.new(key.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)


class ManagedAuthSessionRequest(BaseModel):
    name: str = Field(..., min_length=1)
    connector_id: str | None = Field(default=None, alias="connectorId")

    model_config = {"populate_by_name": True}


class ManagedAuthSessionResponse(BaseModel):
    connector_id: str = Field(alias="connectorId")
    session_token: str = Field(alias="sessionToken")
    attempt_id: str = Field(alias="attemptId")
    expires_at: str | None = Field(default=None, alias="expiresAt")

    model_config = {"populate_by_name": True}


@router.get("/catalog")
def managed_auth_catalog(
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    from app.services.managed_service_desk_tools import MANAGED_SERVICE_DESK_TOOL_EXECUTORS
    from app.services.managed_security_tools import MANAGED_SECURITY_TOOL_EXECUTORS
    actions = set(MANAGED_SERVICE_DESK_TOOL_EXECUTORS) | set(MANAGED_SECURITY_TOOL_EXECUTORS)
    return {
        "configured": nango_configured(settings) and bool(settings.nango_webhook_signing_key.strip()),
        "connectors": [{"vendor": spec.vendor, "actions": sorted(a for a in actions if a.startswith(spec.vendor + ".")),
                        "support": "actions_supported" if any(a.startswith(spec.vendor + ".") for a in actions) else "authorization_only"}
                       for spec in NANGO_CONNECTOR_REGISTRY.values()],
    }


@router.get("/{connector_id}/status")
def managed_auth_status(
    connector_id: str,
    _member: Annotated[tuple, Depends(require_org_member)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _, org_id, _role = _member
    client = shared_service_client(settings, create_client)
    row = (client.table("connectors").select("config, status")
           .eq("id", connector_id).eq("org_id", org_id).eq("environment", environment_name)
           .is_("deleted_at", "null").limit(1).execute())
    if not row.data:
        raise HTTPException(status_code=404, detail="Connector not found")
    config = safe_normalize_stored_dict(dict(row.data[0]), key="config")
    connected = (row.data[0].get("status") == "active" and config.get("auth_provider") == "managed"
                 and bool(config.get("managed_connection_id")))
    return {"connected": bool(connected), "status": str(row.data[0].get("status") or "pending_auth"),
            "confirmedAttemptId": config.get("managed_auth_confirmed_attempt_id")}


@router.post("/{vendor}/session", response_model=ManagedAuthSessionResponse)
def create_managed_auth_session(
    vendor: str,
    body: ManagedAuthSessionRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ManagedAuthSessionResponse:
    user, org_id = _admin
    spec = get_nango_connector_spec(vendor)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported connector")
    if not nango_configured(settings) or not settings.nango_webhook_signing_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Managed connector authorization is not configured", "MANAGED_AUTH_NOT_CONFIGURED"),
        )

    client = shared_service_client(settings, create_client)
    connector_id = body.connector_id
    reconnect = bool(connector_id)
    if connector_id:
        existing = (
            client.table("connectors")
            .select("id, vendor, type, config, status, environment")
            .eq("org_id", org_id)
            .eq("id", connector_id)
            .eq("environment", environment_name)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
        row = existing.data[0]
        stored_vendor = str(row.get("vendor") or row.get("type") or "").strip().lower()
        if stored_vendor != spec.vendor:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connector vendor mismatch")
    else:
        try:
            # Managed auth never reuses a connector from another environment.
            found = (client.table("connectors").select("id, config, status")
                     .eq("org_id", org_id).eq("environment", environment_name)
                     .eq("vendor", spec.vendor).eq("name", body.name.strip())
                     .is_("deleted_at", "null").limit(1).execute())
            if found.data:
                connector_id = str(found.data[0]["id"])
                reconnect, is_new = True, False
            else:
                created = client.table("connectors").insert({
                    "org_id": org_id, "vendor": spec.vendor, "type": spec.vendor,
                    "name": body.name.strip(), "environment": environment_name,
                    "status": "pending_auth", "sync_frequency": "1h",
                    "description": spec.description, "config": {"auth_provider": "managed"},
                }).execute()
                if not created.data:
                    raise HTTPException(status_code=500, detail="Connector create failed")
                connector_id, reconnect, is_new = str(created.data[0]["id"]), False, True
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            if is_connector_type_schema_error(exc):
                raise_connector_type_schema_error(exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail("Connector create failed; check the connector name and configuration", "CONNECTOR_CREATE_FAILED"),
            ) from exc
        if is_new:
            write_audit_event(
                client,
                org_id=org_id,
                actor_id=user["user_id"],
                action="connector.created",
                resource_type="connector",
                resource_id=str(connector_id),
                metadata={
                    "environment": environment_name,
                    "auth": "managed_oauth",
                    "provider": spec.vendor,
                },
            )

    # Read the row created/reused for this environment. Never discard
    # provider settings or an existing connection when a reconnect is cancelled.
    stored = (client.table("connectors").select("config, status")
              .eq("id", str(connector_id)).eq("org_id", org_id)
              .eq("environment", environment_name).is_("deleted_at", "null")
              .limit(1).execute())
    if not stored.data:
        raise HTTPException(status_code=404, detail="Connector not found")
    config = safe_normalize_stored_dict(dict(stored.data[0]), key="config")
    attempt_id = str(uuid4())
    config["managed_auth_attempt_id"] = attempt_id
    config.update({"auth_type": "oauth", "auth_provider": "managed",
                   "managed_integration_id": spec.integration_id})
    connection_id = str(config.get("managed_connection_id") or "").strip() or None
    client.table("connectors").update({"config": config}).eq(
        "id", str(connector_id)).eq("org_id", org_id).eq(
        "environment", environment_name).execute()

    try:
        data = create_connect_session(
            settings,
            end_user_id=str(user["user_id"]),
            end_user_email=str(user.get("email") or "") or None,
            organization_id=str(org_id),
            organization_name=None,
            integration_ids=[spec.integration_id],
            connector_id=str(connector_id),
            connection_id=connection_id,
            attempt_id=attempt_id,
        )
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_detail(
                "Connector authorization session failed; check integration configuration",
                "MANAGED_AUTH_SESSION_FAILED",
            ),
        ) from exc

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="connector.oauth.reconnect_started" if reconnect else "connector.oauth.started",
        resource_type="connector",
        resource_id=str(connector_id),
        metadata={
            "provider": spec.vendor,
            "environment": environment_name,
            "auth_provider": "managed",
        },
    )
    return ManagedAuthSessionResponse(
        connector_id=str(connector_id),
        session_token=str(data["token"]),
        attempt_id=attempt_id,
        expires_at=str(data.get("expires_at") or "") or None,
    )


@router.post("/webhook/nango")
async def handle_nango_auth_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, bool]:
    """Persist managed connection identity after Nango authorization succeeds.

    Nango credentials remain in Nango. Gravitre stores only the opaque connection
    id required for subsequent proxy calls, scoped to the connector/org pair
    carried in the signed connect-session tags.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Nango-Hmac-Sha256")
    if not _verify_nango_webhook_signature(
        raw_body,
        signature,
        settings.nango_webhook_signing_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail("Invalid managed connector webhook signature", "MANAGED_AUTH_WEBHOOK_INVALID"),
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("Invalid managed connector webhook payload", "MANAGED_AUTH_WEBHOOK_INVALID"),
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid managed connector webhook payload")
    if payload.get("type") != "auth":
        return {"ok": True}
    if payload.get("success") is not True:
        return {"ok": True}

    operation = str(payload.get("operation") or "").strip().lower()
    if operation not in {"creation", "override"}:
        return {"ok": True}

    tags = payload.get("tags") if isinstance(payload.get("tags"), dict) else {}
    org_id = str(tags.get("organization_id") or "").strip()
    connector_id = str(tags.get("connector_id") or "").strip()
    connection_id = str(payload.get("connectionId") or payload.get("connection_id") or "").strip()
    if not org_id or not connector_id or not connection_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(
                "Managed connector webhook is missing required connection tags",
                "MANAGED_AUTH_WEBHOOK_INCOMPLETE",
            ),
        )

    client = shared_service_client(settings, create_client)
    existing = (
        client.table("connectors")
        .select("id, org_id, vendor, type, config, environment")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )

    row = dict(existing.data[0])
    config = safe_normalize_stored_dict(row, key="config")
    integration_id = str(
        payload.get("providerConfigKey")
        or payload.get("provider_config_key")
        or config.get("managed_integration_id")
        or ""
    ).strip()
    spec = get_nango_connector_spec(str(row.get("vendor") or row.get("type") or ""))
    if config.get("auth_provider") != "managed" or spec is None:
        raise HTTPException(status_code=400, detail="Connector is not managed")
    expected_integration_id = spec.integration_id
    if integration_id != expected_integration_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(
                "Managed connector integration mismatch",
                "MANAGED_AUTH_INTEGRATION_MISMATCH",
            ),
        )

    pending_attempt = config.get("managed_auth_attempt_id")
    if pending_attempt and tags.get("auth_attempt_id") != pending_attempt:
        raise HTTPException(status_code=409, detail="Stale connector authorization attempt")
    if pending_attempt:
        config["managed_auth_confirmed_attempt_id"] = pending_attempt

    config["auth_type"] = "oauth"
    config["auth_provider"] = "managed"
    config["managed_connection_id"] = connection_id
    if integration_id:
        config["managed_integration_id"] = integration_id

    update = client.table("connectors").update({"config": config, "status": "active"}).eq(
        "id", connector_id).eq("org_id", org_id).is_("deleted_at", "null")
    if pending_attempt:
        update = update.eq("config->>managed_auth_attempt_id", str(pending_attempt))
    if not update.execute().data:
        raise HTTPException(status_code=409, detail="Connector authorization changed; retry the current session")

    actor_id = str(tags.get("end_user_id") or "").strip() or None
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action="connector.oauth.connected",
        resource_type="connector",
        resource_id=connector_id,
        metadata={
            "provider": str(row.get("vendor") or row.get("type") or ""),
            "environment": row.get("environment"),
            "auth_provider": "managed",
            "operation": operation,
        },
    )
    return {"ok": True}
