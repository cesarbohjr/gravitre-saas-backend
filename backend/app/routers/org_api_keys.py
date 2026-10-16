"""Org-scoped API key management endpoints (External Distribution).

All endpoints require the caller to be an org admin or platform admin.
The raw key is returned exactly once on creation and never again.

POST   /api/org/{org_id}/api-keys         Issue a new key
GET    /api/org/{org_id}/api-keys         List active keys (no raw values)
DELETE /api/org/{org_id}/api-keys/{id}    Revoke a key
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.api_key_auth import VALID_SCOPES, generate_api_key, validate_scopes
from app.auth.dependencies import get_current_user
from app.auth.platform_admin import ORG_ADMIN_ROLES, is_platform_admin
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.workflows.audit import write_audit_event

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

logger = get_logger(__name__)
router = APIRouter(prefix="/api/org/{org_id}/api-keys", tags=["api_keys"])

_MAX_ACTIVE_KEYS_PER_ORG = 20


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CreateApiKeyRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120, description="Human-readable key name")
    scopes: list[str] = Field(default_factory=list, description=f"Subset of {sorted(VALID_SCOPES)}")
    expires_in_days: int | None = Field(
        default=None, ge=1, le=3650,
        description="Expiry in days from now; omit for no expiry",
    )
    test: bool = Field(default=False, description="Issue a test key (grav_test_ prefix)")


class CreateApiKeyResponse(BaseModel):
    id: str
    label: str
    key: str           # raw key — shown ONCE, never stored
    key_prefix: str    # safe to display later
    scopes: list[str]
    expires_at: str | None
    created_at: str


class ApiKeySummary(BaseModel):
    id: str
    label: str
    key_prefix: str
    scopes: list[str]
    expires_at: str | None
    last_used_at: str | None
    created_at: str
    created_by: str


class ListApiKeysResponse(BaseModel):
    keys: list[ApiKeySummary]


class RevokeApiKeyResponse(BaseModel):
    id: str
    revoked: bool


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _require_org_admin(client: Any, user_id: str, org_id: str) -> None:
    """Raise 403 unless the user is an org admin/owner or platform admin."""
    if is_platform_admin(client, user_id):
        return
    try:
        resp = (
            client.table("organization_members")
            .select("role")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Role check failed") from exc

    if not resp.data or resp.data[0].get("role") not in ORG_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Org admin role required to manage API keys")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def create_api_key(
    org_id: str,
    body: CreateApiKeyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CreateApiKeyResponse:
    """Issue a new org-scoped API key. The raw key is returned once only."""
    client = shared_service_client(settings, create_client)
    user_id: str = current_user["user_id"]
    _require_org_admin(client, user_id, org_id)

    # Validate scopes.
    try:
        scopes = validate_scopes(body.scopes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Enforce per-org key cap.
    try:
        count_resp = (
            client.table("org_api_keys")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .is_("revoked_at", "null")
            .execute()
        )
        active_count = getattr(count_resp, "count", None) or len(count_resp.data or [])
        if active_count >= _MAX_ACTIVE_KEYS_PER_ORG:
            raise HTTPException(
                status_code=409,
                detail=f"Org has reached the limit of {_MAX_ACTIVE_KEYS_PER_ORG} active API keys. "
                       "Revoke unused keys before issuing new ones.",
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Failed to check key count") from exc

    raw_key, key_prefix, key_hash = generate_api_key(test=body.test)

    expires_at: str | None = None
    if body.expires_in_days:
        from datetime import timedelta
        expires_at = (datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)).isoformat()

    try:
        resp = client.table("org_api_keys").insert({
            "org_id": org_id,
            "created_by": user_id,
            "label": body.label,
            "key_prefix": key_prefix,
            "key_hash": key_hash,
            "scopes": scopes,
            "expires_at": expires_at,
        }).execute()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Failed to store API key") from exc

    if not resp.data:
        raise HTTPException(status_code=500, detail="No row returned after insert")

    row = resp.data[0]
    key_id = str(row["id"])

    write_audit_event(client, {
        "actor_user_id": user_id,
        "action": "org_api_key.create",
        "resource_type": "org_api_key",
        "resource_id": key_id,
        "metadata": {
            "org_id": org_id,
            "label": body.label,
            "scopes": scopes,
            "expires_at": expires_at,
            "key_prefix": key_prefix,
        },
    })
    logger.info("org_api_key_created org_id=%s key_id=%s scopes=%s", org_id, key_id, scopes)

    return CreateApiKeyResponse(
        id=key_id,
        label=body.label,
        key=raw_key,
        key_prefix=key_prefix,
        scopes=scopes,
        expires_at=expires_at,
        created_at=str(row.get("created_at") or datetime.now(timezone.utc).isoformat()),
    )


@router.get("")
async def list_api_keys(
    org_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ListApiKeysResponse:
    """List active (non-revoked) API keys for the org. Raw values are never returned."""
    client = shared_service_client(settings, create_client)
    user_id: str = current_user["user_id"]
    _require_org_admin(client, user_id, org_id)

    try:
        resp = (
            client.table("org_api_keys")
            .select("id, label, key_prefix, scopes, expires_at, last_used_at, created_at, created_by")
            .eq("org_id", org_id)
            .is_("revoked_at", "null")
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Failed to list API keys") from exc

    keys = [
        ApiKeySummary(
            id=str(row["id"]),
            label=str(row.get("label") or ""),
            key_prefix=str(row.get("key_prefix") or ""),
            scopes=list(row.get("scopes") or []),
            expires_at=str(row["expires_at"]) if row.get("expires_at") else None,
            last_used_at=str(row["last_used_at"]) if row.get("last_used_at") else None,
            created_at=str(row.get("created_at") or ""),
            created_by=str(row.get("created_by") or ""),
        )
        for row in (resp.data or [])
    ]
    return ListApiKeysResponse(keys=keys)


@router.delete("/{key_id}")
async def revoke_api_key(
    org_id: str,
    key_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RevokeApiKeyResponse:
    """Revoke an API key immediately. The key stops working on the next request."""
    client = shared_service_client(settings, create_client)
    user_id: str = current_user["user_id"]
    _require_org_admin(client, user_id, org_id)

    # Verify the key belongs to this org and is not already revoked.
    try:
        check = (
            client.table("org_api_keys")
            .select("id, revoked_at")
            .eq("id", key_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="DB lookup failed") from exc

    if not check.data:
        raise HTTPException(status_code=404, detail="API key not found for this org")

    if check.data[0].get("revoked_at"):
        # Already revoked — idempotent.
        return RevokeApiKeyResponse(id=key_id, revoked=True)

    try:
        client.table("org_api_keys").update({
            "revoked_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", key_id).eq("org_id", org_id).execute()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Failed to revoke API key") from exc

    write_audit_event(client, {
        "actor_user_id": user_id,
        "action": "org_api_key.revoke",
        "resource_type": "org_api_key",
        "resource_id": key_id,
        "metadata": {"org_id": org_id},
    })
    logger.info("org_api_key_revoked org_id=%s key_id=%s", org_id, key_id)
    return RevokeApiKeyResponse(id=key_id, revoked=True)
