"""BE-00: Auth endpoints. GET /api/auth/me requires auth."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from supabase import create_client
from app.core.db import shared_service_client
from app.core.safe_dict import safe_normalize_stored_dict

from app.auth.dependencies import get_current_user, get_org_context
from app.auth.jwt_verify import decode_supabase_jwt
from app.billing.entitlements import compute_app_access, normalize_billing_status
from app.billing.service import DEFAULT_PLAN_CODE, UNSET, get_org_billing
from app.config import Settings, get_settings
from app.services.org_membership import load_user_organizations, pick_default_org_id, load_user_primary_org_id
from app.core.org_state_cache import (
    auth_me_cache,
    cache_allowed,
    invalidate_user_state,
    org_tag,
    user_tag,
)
from app.core.supabase_response import response_error

router = APIRouter(prefix="/api/auth", tags=["auth"])


class ProfilePreferences(BaseModel):
    """Per-person display preferences, kept on the Supabase auth user."""

    theme: Literal["light", "dark", "system"] | None = None
    compact_tables: bool | None = None


class UserProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = None
    department: str | None = None
    location: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)
    bio: str | None = Field(default=None, max_length=280)
    preferences: ProfilePreferences | None = None


# Profile fields with no public.users column live in the auth user's
# user_metadata under one namespaced key, so OAuth metadata (name, picture,
# phone from a provider) is never overwritten and no migration is needed.
PROFILE_METADATA_KEY = "gravitre_profile"
PROFILE_METADATA_FIELDS: tuple[str, ...] = ("phone", "location", "timezone", "bio")
PROFILE_PREFERENCE_DEFAULTS: dict = {"theme": None, "compact_tables": False}


def _auth_user_object(response):
    user = getattr(response, "user", None)
    if user is None and isinstance(response, dict):
        user = response.get("user", response)
    return user


def _attr(obj, name: str):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _load_auth_profile(client, auth_user_id: str) -> dict | None:
    """Namespaced profile metadata and email confirmation from the auth user.

    Returns None when the auth admin API is unavailable (callers then report the
    fields as unknown instead of guessing).
    """
    try:
        response = client.auth.admin.get_user_by_id(auth_user_id)
    except Exception:  # noqa: BLE001
        return None
    user = _auth_user_object(response)
    if user is None:
        return None
    metadata = _attr(user, "user_metadata")
    stored = metadata.get(PROFILE_METADATA_KEY) if isinstance(metadata, dict) else None
    confirmed_at = _attr(user, "email_confirmed_at") or _attr(user, "confirmed_at")
    return {
        "profile": dict(stored) if isinstance(stored, dict) else {},
        "email_confirmed": bool(confirmed_at) if isinstance(confirmed_at, (str, datetime)) else False,
    }


def _profile_fields(stored: dict | None) -> dict:
    stored = stored if isinstance(stored, dict) else {}
    prefs = stored.get("preferences") if isinstance(stored.get("preferences"), dict) else {}
    theme = prefs.get("theme")
    return {
        **{field: (stored.get(field) or None) for field in PROFILE_METADATA_FIELDS},
        "preferences": {
            "theme": theme if theme in ("light", "dark", "system") else PROFILE_PREFERENCE_DEFAULTS["theme"],
            "compact_tables": bool(prefs.get("compact_tables", PROFILE_PREFERENCE_DEFAULTS["compact_tables"])),
        },
    }


def _save_auth_profile(client, auth_user_id: str, fields: dict, preferences: dict | None) -> dict:
    """Merge profile fields and preferences into the auth user's metadata."""
    current = _load_auth_profile(client, auth_user_id)
    if current is None:
        # Never overwrite what we could not read.
        raise HTTPException(status_code=502, detail="Unable to load your profile to update it. Try again.")
    merged = safe_normalize_stored_dict(current, key="profile")
    for field, value in fields.items():
        cleaned = value.strip() if isinstance(value, str) else value
        if cleaned:
            merged[field] = cleaned
        else:
            merged.pop(field, None)
    if preferences:
        prefs = safe_normalize_stored_dict(merged, key="preferences")
        prefs.update(preferences)
        merged["preferences"] = prefs
    try:
        client.auth.admin.update_user_by_id(auth_user_id, {"user_metadata": {PROFILE_METADATA_KEY: merged}})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Unable to save your profile: {exc}") from exc
    return merged


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


def _is_missing_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return "does not exist" in message or "column" in message


def _resolve_role(client, org_id: str | None, user_id: str) -> str | None:
    if not org_id:
        return None
    role_resp = (
        client.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if role_resp.data and len(role_resp.data) > 0:
        return (role_resp.data[0].get("role") or "").strip().lower() or None
    return None


def _load_org_settings_row(client, org_id: str) -> dict | None:
    org_resp = (
        client.table("organizations")
        .select("settings")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    if not org_resp.data:
        return None
    return org_resp.data[0].get("settings") or {}


def _load_onboarding_summary(client, org_id: str | None, *, org_settings=UNSET) -> dict:
    if not org_id:
        return {"seeded": False, "completed_at": None, "checklist_dismissed": False}
    if org_settings is UNSET:
        org_settings = _load_org_settings_row(client, org_id)
    if org_settings is None:
        return {"seeded": False, "completed_at": None, "checklist_dismissed": False}
    settings = org_settings
    onboarding = settings.get("onboarding") if isinstance(settings, dict) else {}
    if not isinstance(onboarding, dict):
        onboarding = {}
    return {
        "seeded": bool(onboarding.get("seeded")),
        "completed_at": onboarding.get("completed_at"),
        "checklist_dismissed": bool(onboarding.get("checklist_dismissed")),
    }


def _load_billing_summary(client, org_id: str | None, *, org_settings=UNSET) -> dict:
    if not org_id:
        return {
            "status": "inactive",
            "plan_code": DEFAULT_PLAN_CODE,
            "can_access_app": False,
        }
    billing_row = get_org_billing(client, org_id)
    billing = billing_row or {
        "plan_code": DEFAULT_PLAN_CODE,
        "billing_status": "trialing",
    }
    status = normalize_billing_status(billing.get("billing_status"))
    trial_ends_at = billing.get("current_period_end")
    from app.billing.entitlement_service import get_org_billing_state

    state_kwargs: dict = {"billing": billing_row}
    if org_settings is not UNSET:
        state_kwargs["org_settings"] = (
            org_settings if isinstance(org_settings, dict) or org_settings is None else {}
        )
    billing_state = get_org_billing_state(client, org_id, **state_kwargs)
    if billing_state["is_blocked"]:
        access = {
            "can_access_app": False,
            "requires_upgrade": True,
            "upgrade_reason": "trial_expired"
            if billing_state["status"] == "trial_expired"
            else "payment_past_due"
            if billing_state["status"] == "past_due"
            else "subscription_cancelled",
        }
    else:
        access = compute_app_access(status, trial_ends_at=trial_ends_at)
    return {
        "status": billing_state.get("status") or status,
        "plan_code": (billing.get("plan_code") or DEFAULT_PLAN_CODE).strip().lower(),
        "can_access_app": access["can_access_app"],
        "trial_ends_at": trial_ends_at or billing_state.get("trial_ends_at"),
    }


def _resolve_user_row(client, auth_user_id: str) -> dict:
    selects = (
        "id, org_id, email, full_name, avatar_url, job_title, department, "
        "role, created_at, updated_at",
        # Pre-migration fallback until job_title/department columns exist.
        "id, org_id, email, full_name, avatar_url, role, created_at, updated_at",
    )
    last_exc: Exception | None = None
    for select_cols in selects:
        try:
            user_resp = (
                client.table("users")
                .select(select_cols)
                .eq("auth_user_id", auth_user_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _is_missing_error(exc):
                continue
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if _is_missing_error(response_error(user_resp)):
            continue
        if not user_resp.data:
            return {}
        return dict(user_resp.data[0])
    if last_exc and not _is_missing_error(last_exc):
        raise HTTPException(status_code=500, detail=str(last_exc)) from last_exc
    return {}


@router.get("/me")
def me(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """GET /api/auth/me — returns backwards-compatible + structured user payload.

    Cached per (user, org selection, email) for ORG_STATE_CACHE_TTL_SECONDS on
    the shared production client; profile, membership, org and billing writes
    invalidate the user's / org's entries.
    """
    client = shared_service_client(settings, create_client)
    auth_user_id = str(current_user["user_id"])
    cacheable = auth_me_cache.enabled and cache_allowed(client)
    cache_key = (auth_user_id, str(org_id or ""), str(current_user.get("email") or ""))
    if cacheable:
        cached = auth_me_cache.get(cache_key)
        if cached is not None:
            return cached
        cache_token = auth_me_cache.token()
    payload = _compute_me(client, current_user, org_id)
    if cacheable:
        tags = {user_tag(auth_user_id)}
        if payload.get("org_id"):
            tags.add(org_tag(payload["org_id"]))
        if org_id:
            tags.add(org_tag(org_id))
        for org in payload.get("organizations") or []:
            if org.get("id"):
                tags.add(org_tag(org["id"]))
        auth_me_cache.set(cache_key, payload, tags=tags, token=cache_token)
    return payload


def _compute_me(client, current_user: dict, org_id: str | None) -> dict:
    from app.auth.platform_admin import is_platform_admin
    from app.services.org_membership import ensure_founder_admin_access

    auth_user_id = current_user["user_id"]
    user_row = _resolve_user_row(client, auth_user_id)
    organizations = load_user_organizations(client, auth_user_id, include_settings=True)
    resolved_org_id = org_id or pick_default_org_id(
        [org["id"] for org in organizations],
        primary_org_id=str(user_row.get("org_id")) if user_row.get("org_id") else load_user_primary_org_id(client, auth_user_id),
    )
    promoted = ensure_founder_admin_access(
        client,
        user_id=auth_user_id,
        email=current_user.get("email") or user_row.get("email"),
        org_id=resolved_org_id,
    )
    if promoted:
        # Reload after founder promotion so role reflects owner.
        organizations = load_user_organizations(client, auth_user_id, include_settings=True)
    # organizations already carries the membership role and org settings; only
    # fall back to dedicated reads when the resolved org is not among them
    # (e.g. a platform admin viewing another org).
    current_org_row = next((org for org in organizations if org.get("id") == resolved_org_id), None)
    if current_org_row is not None and current_org_row.get("role"):
        role = str(current_org_row.get("role") or "").strip().lower() or None
    else:
        role = _resolve_role(client, resolved_org_id, auth_user_id)

    auth_profile = _load_auth_profile(client, auth_user_id)
    merged_user = {
        "id": auth_user_id,
        "email": user_row.get("email") or current_user.get("email"),
        "full_name": user_row.get("full_name"),
        "avatar_url": user_row.get("avatar_url"),
        "job_title": user_row.get("job_title"),
        "department": user_row.get("department"),
        "role": user_row.get("role") or role,
        "created_at": user_row.get("created_at"),
        "updated_at": user_row.get("updated_at"),
        **_profile_fields(auth_profile["profile"] if auth_profile else None),
        # None when the auth admin API could not be read: the UI then shows no badge.
        "email_confirmed": auth_profile["email_confirmed"] if auth_profile else None,
    }

    org_name_by_id = {org["id"]: org.get("name") for org in organizations}
    current_org = (
        {"id": resolved_org_id, "name": org_name_by_id.get(resolved_org_id) or "Current Organization"}
        if resolved_org_id
        else None
    )
    org_settings = UNSET
    if current_org_row is not None and "settings" in current_org_row:
        org_settings = current_org_row.get("settings") or {}
    if resolved_org_id and org_settings is UNSET:
        org_settings = _load_org_settings_row(client, resolved_org_id)
    onboarding = _load_onboarding_summary(client, resolved_org_id, org_settings=org_settings)
    billing = _load_billing_summary(client, resolved_org_id, org_settings=org_settings)

    return {
        "user_id": auth_user_id,
        "org_id": resolved_org_id,
        "email": current_user.get("email"),
        "role": role,
        "platformAdmin": is_platform_admin(client, auth_user_id),
        "user": merged_user,
        "organizations": [
            {"id": org["id"], "name": org.get("name"), "role": org.get("role")}
            for org in organizations
        ],
        "current_org": current_org,
        "onboarding": onboarding,
        "billing": billing,
    }


@router.patch("/me")
def update_me(
    body: UserProfileUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = shared_service_client(settings, create_client)
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    preferences = {k: v for k, v in (payload.pop("preferences", None) or {}).items() if v is not None}
    if not payload and not preferences:
        return {"id": current_user["user_id"], "email": current_user.get("email")}

    base = {"id": current_user["user_id"], "email": current_user.get("email")}
    # Phone, location, time zone, bio and preferences have no public.users
    # column: they are kept on the auth user's metadata (merged, never replaced).
    meta_fields = {k: payload.pop(k) for k in PROFILE_METADATA_FIELDS if k in payload}
    if meta_fields or preferences:
        stored = _save_auth_profile(client, current_user["user_id"], meta_fields, preferences)
        invalidate_user_state(current_user["user_id"])
        base.update(_profile_fields(stored))

    # Only persist columns that exist on public.users.
    allowed = {"full_name", "avatar_url", "job_title", "department"}
    db_payload = {k: v for k, v in payload.items() if k in allowed}
    if not db_payload:
        return {**base, **payload}

    # Bug fix: .update() returns SyncFilterRequestBuilder, which has no
    # .select()/.limit() — chaining them raised AttributeError -> HTTP 500.
    # .update() already returns the full updated row(s) by default.
    update_resp = (
        client.table("users")
        .update(db_payload)
        .eq("auth_user_id", current_user["user_id"])
        .execute()
    )
    invalidate_user_state(current_user["user_id"])
    update_error = response_error(update_resp)
    if _is_missing_error(update_error):
        return {**base, **payload}
    if update_error:
        raise HTTPException(status_code=500, detail=str(update_error))
    row = (update_resp.data or [{}])[0]
    return {**base, **dict(row)}


@router.post("/change-password")
def change_password(
    body: PasswordChangeRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    email = current_user.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Unable to resolve current user email")

    anon_client = create_client(settings.supabase_url, settings.supabase_anon_key)
    try:
        anon_client.auth.sign_in_with_password(
            {"email": email, "password": body.current_password}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Current password is invalid")

    admin_client = shared_service_client(settings, create_client)
    try:
        admin_client.auth.admin.update_user_by_id(
            current_user["user_id"],
            {"password": body.new_password},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to change password: {exc}")
    return {"ok": True}


def _current_session_id(request: Request, settings: Settings) -> str | None:
    """Supabase session id (the access token's session_id claim) for this request."""
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    try:
        claims = decode_supabase_jwt(header[7:].strip(), settings)
    except Exception:  # noqa: BLE001
        return None
    session_id = claims.get("session_id")
    return str(session_id) if session_id else None


def _request_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


@router.get("/sessions")
def list_sessions(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = shared_service_client(settings, create_client)
    current_session_id = _current_session_id(request, settings)
    sessions: list[dict] = []
    try:
        sessions_resp = (
            client.schema("auth")
            .table("sessions")
            .select("id, ip, user_agent, created_at, updated_at")
            .eq("user_id", current_user["user_id"])
            .order("updated_at", desc=True)
            .limit(20)
            .execute()
        )
        if sessions_resp.data:
            for idx, row in enumerate(sessions_resp.data):
                session_id = str(row.get("id") or "")
                sessions.append(
                    {
                        "id": session_id,
                        "device": str(row.get("user_agent") or "Unknown device"),
                        "user_agent": row.get("user_agent"),
                        "ip": str(row.get("ip") or "Unknown IP"),
                        "created_at": row.get("created_at"),
                        "last_active": str(row.get("updated_at") or row.get("created_at") or ""),
                        # The token names its own session; without that claim the
                        # most recently active session is the best guess.
                        "current": session_id == current_session_id if current_session_id else idx == 0,
                    }
                )
    except Exception:
        sessions = []

    if not sessions:
        user_agent = request.headers.get("user-agent")
        sessions = [
            {
                "id": "current",
                "device": user_agent or "Current browser",
                "user_agent": user_agent,
                "ip": _request_ip(request),
                "created_at": None,
                "last_active": datetime.now(timezone.utc).isoformat(),
                "current": True,
            }
        ]
    return {"sessions": sessions}


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = shared_service_client(settings, create_client)
    try:
        client.schema("auth").table("sessions").delete().eq("id", session_id).eq(
            "user_id", current_user["user_id"]
        ).execute()
    except Exception:
        pass
    return {"ok": True}


@router.post("/sessions/revoke-all")
def revoke_all_sessions(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Sign out every other session; the session making the request stays signed in."""
    client = shared_service_client(settings, create_client)
    current_session_id = _current_session_id(request, settings)
    try:
        query = client.schema("auth").table("sessions").delete().eq("user_id", current_user["user_id"])
        if current_session_id:
            query = query.neq("id", current_session_id)
        query.execute()
    except Exception:
        pass
    return {"ok": True, "kept_current": bool(current_session_id)}


@router.delete("/avatar")
def delete_avatar(
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = shared_service_client(settings, create_client)
    try:
        client.table("users").update({"avatar_url": None}).eq(
            "auth_user_id", current_user["user_id"]
        ).execute()
    except Exception:
        pass
    invalidate_user_state(current_user["user_id"])
    return {"avatar_url": None}


@router.post("/avatar")
async def upload_avatar(
    avatar: UploadFile = File(...),
    current_user: Annotated[dict, Depends(get_current_user)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> dict:
    content = await avatar.read()
    if not content:
        raise HTTPException(status_code=400, detail="Avatar file is empty")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Avatar exceeds 5MB limit")

    mime = avatar.content_type or "image/png"
    avatar_data_url = f"data:{mime};base64,{base64.b64encode(content).decode('utf-8')}"

    client = shared_service_client(settings, create_client)
    try:
        client.table("users").update({"avatar_url": avatar_data_url}).eq(
            "auth_user_id", current_user["user_id"]
        ).execute()
    except Exception:
        pass
    invalidate_user_state(current_user["user_id"])
    return {"avatar_url": avatar_data_url}
