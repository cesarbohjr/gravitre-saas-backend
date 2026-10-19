"""Settings > API keys: create, list, rotate and revoke workspace API keys.

Rows live in ``public.api_keys`` (only a SHA-256 hash of the secret is
stored). The table has no scope or expiry columns, so each key's scope,
expiry and last four characters live in
``organizations.settings["apiKeyPolicies"][<key id>]`` (no migration).

Nothing in the API authenticates with these keys yet; when that path ships it
must call :func:`api_key_is_usable` so expired and revoked keys are rejected
and :data:`SCOPES` decide what a key can do.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import require_admin
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.org_state_cache import invalidate_org_state
from app.core.supabase_response import response_error
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/settings/api-keys", tags=["settings"])

POLICIES_KEY = "apiKeyPolicies"
KEY_PREFIX = "gv_live_"
SCOPES: tuple[str, ...] = ("read", "read_write", "workflows")
EXPIRY_DAYS: dict[str, int | None] = {"30d": 30, "90d": 90, "1y": 365, "never": None}
COLUMNS = "id, org_id, name, key_prefix, status, last_used_at, created_at, updated_at"


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    scope: str = "read"
    expires_in: str = "90d"


class ApiKeyStatusRequest(BaseModel):
    id: str = Field(..., min_length=1)
    status: str = "revoked"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_api_key(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(24)


def expires_at_for(expires_in: str, now: datetime | None = None) -> str | None:
    days = EXPIRY_DAYS[expires_in]
    if days is None:
        return None
    return ((now or _now()) + timedelta(days=days)).isoformat()


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def api_key_is_usable(row: dict[str, Any], policy: dict[str, Any] | None, now: datetime | None = None) -> bool:
    """True only for an active key whose expiry (if any) is still in the future."""
    if str(row.get("status") or "") != "active":
        return False
    expires = _parse_time((policy or {}).get("expiresAt"))
    return expires is None or expires > (now or _now())


def _org_settings(client: Any, org_id: str) -> dict[str, Any]:
    rows = client.table("organizations").select("id, settings").eq("id", org_id).limit(1).execute().data or []
    raw = rows[0].get("settings") if rows else None
    return dict(raw) if isinstance(raw, dict) else {}


def _policies(org_settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = org_settings.get(POLICIES_KEY)
    return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)} if isinstance(raw, dict) else {}


def _save_policy(client: Any, org_id: str, key_id: str, policy: dict[str, Any] | None) -> None:
    org_settings = _org_settings(client, org_id)
    policies = _policies(org_settings)
    if policy is None:
        policies.pop(key_id, None)
    else:
        policies[key_id] = policy
    org_settings[POLICIES_KEY] = policies
    client.table("organizations").update({"settings": org_settings}).eq("id", org_id).execute()
    invalidate_org_state(org_id)


def _serialize(row: dict[str, Any], policy: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any]:
    policy = policy or {}
    scope = policy.get("scope")
    status = str(row.get("status") or "active")
    expires_at = policy.get("expiresAt")
    expired = status == "active" and not api_key_is_usable(row, policy, now)
    return {
        "id": str(row.get("id")),
        "org_id": row.get("org_id"),
        "name": row.get("name") or "API key",
        "key_prefix": row.get("key_prefix") or "",
        "last4": policy.get("last4"),
        "status": status,
        # Keys created before scopes existed have no stored scope: report it as unknown.
        "scope": scope if scope in SCOPES else None,
        "expires_at": expires_at,
        "expired": expired,
        "last_used_at": row.get("last_used_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _key_row(client: Any, org_id: str, key_id: str) -> dict[str, Any]:
    rows = client.table("api_keys").select(COLUMNS).eq("org_id", org_id).eq("id", key_id).limit(1).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="API key not found")
    return dict(rows[0])


@router.get("")
def list_api_keys_route(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = admin
    client = shared_service_client(settings, create_client)
    result = client.table("api_keys").select(COLUMNS).eq("org_id", org_id).order("created_at", desc=True).execute()
    err = response_error(result)
    if err:
        raise HTTPException(status_code=500, detail=str(err))
    policies = _policies(_org_settings(client, org_id))
    now = _now()
    return {"apiKeys": [_serialize(row, policies.get(str(row.get("id"))), now) for row in result.data or []]}


@router.post("")
def create_api_key_route(
    body: ApiKeyCreateRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Give the key a name")
    if body.scope not in SCOPES:
        raise HTTPException(status_code=400, detail="scope must be one of read, read_write, workflows")
    if body.expires_in not in EXPIRY_DAYS:
        raise HTTPException(status_code=400, detail="expires_in must be one of 30d, 90d, 1y, never")

    client = shared_service_client(settings, create_client)
    secret = generate_api_key()
    insert = (
        client.table("api_keys")
        .insert(
            {
                "org_id": org_id,
                "name": name,
                "key_prefix": secret[: len(KEY_PREFIX) + 4],
                "key_hash": hash_api_key(secret),
                "status": "active",
                "created_by": user["user_id"],
            }
        )
        .execute()
    )
    err = response_error(insert)
    if err or not insert.data:
        raise HTTPException(status_code=500, detail=str(err or "Could not create the API key"))
    row = dict(insert.data[0])
    policy = {"scope": body.scope, "expiresAt": expires_at_for(body.expires_in), "last4": secret[-4:]}
    _save_policy(client, org_id, str(row["id"]), policy)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="api_key.created",
        resource_type="api_key",
        resource_id=str(row["id"]),
        metadata={"name": name, "scope": body.scope, "expiresAt": policy["expiresAt"]},
    )
    # The full secret is returned exactly once, here.
    return {"apiKey": {**_serialize(row, policy), "key": secret}}


@router.patch("")
def update_api_key_status_route(
    body: ApiKeyStatusRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    if body.status != "revoked":
        raise HTTPException(status_code=400, detail="Only revoking a key is supported")
    client = shared_service_client(settings, create_client)
    _key_row(client, org_id, body.id)
    updated = (
        client.table("api_keys")
        .update({"status": "revoked", "updated_at": _now().isoformat()})
        .eq("org_id", org_id)
        .eq("id", body.id)
        .execute()
    )
    err = response_error(updated)
    if err:
        raise HTTPException(status_code=500, detail=str(err))
    row = dict((updated.data or [{}])[0]) or _key_row(client, org_id, body.id)
    row["status"] = "revoked"
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="api_key.revoked",
        resource_type="api_key",
        resource_id=str(body.id),
        metadata={"name": row.get("name")},
    )
    return {"apiKey": _serialize(row, _policies(_org_settings(client, org_id)).get(str(body.id)))}


@router.post("/{key_id}/rotate")
def rotate_api_key_route(
    key_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = shared_service_client(settings, create_client)
    row = _key_row(client, org_id, key_id)
    if str(row.get("status")) != "active":
        raise HTTPException(status_code=400, detail="Only active keys can be rotated")
    secret = generate_api_key()
    updated = (
        client.table("api_keys")
        .update(
            {
                "key_prefix": secret[: len(KEY_PREFIX) + 4],
                "key_hash": hash_api_key(secret),
                "updated_at": _now().isoformat(),
            }
        )
        .eq("org_id", org_id)
        .eq("id", key_id)
        .execute()
    )
    err = response_error(updated)
    if err:
        raise HTTPException(status_code=500, detail=str(err))
    row = {**row, **dict((updated.data or [{}])[0])}
    policy = {**_policies(_org_settings(client, org_id)).get(key_id, {}), "last4": secret[-4:]}
    _save_policy(client, org_id, key_id, policy)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="api_key.rotated",
        resource_type="api_key",
        resource_id=str(key_id),
        metadata={"name": row.get("name")},
    )
    return {"apiKey": {**_serialize(row, policy), "key": secret}}
