"""Managed-auth routes for Nango-backed long-tail connectors.

Nango is an implementation detail. Customer-facing responses use Gravitre connector
language and never expose provider credentials.
"""
from __future__ import annotations

from typing import Annotated
import hashlib
import hmac
import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_environment_context, require_admin
from app.config import Settings, get_settings
from app.connectors.nango_client import create_connect_session, nango_configured
from app.connectors.nango_registry import get_nango_connector_spec
from app.connectors.platform import (
    is_connector_type_schema_error,
    prepare_oauth_connector,
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
    expires_at: str | None = Field(default=None, alias="expiresAt")

    model_config = {"populate_by_name": True}


@router.post("/{vendor}/session", response_model=ManagedAuthSessionResponse)
async def create_managed_auth_session(
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
    if not nango_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Managed connector authorization is not configured", "MANAGED_AUTH_NOT_CONFIGURED"),
        )

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    connector_id = body.connector_id
    reconnect = bool(connector_id)
    if connector_id:
        existing = (
            client.table("connectors")
            .select("id, vendor, type, config")
            .eq("org_id", org_id)
            .eq("id", connector_id)
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
            connector_id, reconnect, is_new = prepare_oauth_connector(
                client,
                org_id=org_id,
                vendor=spec.vendor,
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

    # Persist only routing metadata; Nango/provider credentials remain outside Gravitre.
    client.table("connectors").update(
        {
            "config": {
                "auth_type": "oauth",
                "auth_provider": "managed",
                "managed_integration_id": spec.integration_id,
            },
            "status": "pending_auth",
        }
    ).eq("id", str(connector_id)).eq("org_id", org_id).execute()

    try:
        data = create_connect_session(
            settings,
            end_user_id=str(user["user_id"]),
            end_user_email=str(user.get("email") or "") or None,
            organization_id=str(org_id),
            organization_name=None,
            integration_ids=[spec.integration_id],
            connector_id=str(connector_id),
        )
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_detail(
                f"Connector authorization session failed: {str(exc)[:200]}",
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

    if payload.get("type") != "auth":
        return {"ok": True}
    if not bool(payload.get("success")):
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

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
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
    expected_integration_id = str(config.get("managed_integration_id") or "").strip()
    if expected_integration_id and integration_id and integration_id != expected_integration_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(
                "Managed connector integration mismatch",
                "MANAGED_AUTH_INTEGRATION_MISMATCH",
            ),
        )

    config["auth_type"] = "oauth"
    config["auth_provider"] = "managed"
    config["managed_connection_id"] = connection_id
    if integration_id:
        config["managed_integration_id"] = integration_id

    client.table("connectors").update(
        {
            "config": config,
            "status": "active",
        }
    ).eq("id", connector_id).eq("org_id", org_id).execute()

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
