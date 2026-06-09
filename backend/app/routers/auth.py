"""BE-00: Auth endpoints. GET /api/auth/me requires auth."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.billing.entitlements import compute_app_access, normalize_billing_status
from app.billing.service import DEFAULT_PLAN_CODE, get_org_billing
from app.config import Settings, get_settings
from app.services.org_membership import load_user_organizations, pick_default_org_id, load_user_primary_org_id

router = APIRouter(prefix="/api/auth", tags=["auth"])


class UserProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    job_title: str | None = None
    department: str | None = None
    location: str | None = None
    timezone: str | None = None
    bio: str | None = None


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


def _load_onboarding_summary(client, org_id: str | None) -> dict:
    if not org_id:
        return {"seeded": False, "completed_at": None, "checklist_dismissed": False}
    org_resp = (
        client.table("organizations")
        .select("settings")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    if not org_resp.data:
        return {"seeded": False, "completed_at": None, "checklist_dismissed": False}
    settings = org_resp.data[0].get("settings") or {}
    onboarding = settings.get("onboarding") if isinstance(settings, dict) else {}
    if not isinstance(onboarding, dict):
        onboarding = {}
    return {
        "seeded": bool(onboarding.get("seeded")),
        "completed_at": onboarding.get("completed_at"),
        "checklist_dismissed": bool(onboarding.get("checklist_dismissed")),
    }


def _load_billing_summary(client, org_id: str | None) -> dict:
    if not org_id:
        return {
            "status": "inactive",
            "plan_code": DEFAULT_PLAN_CODE,
            "can_access_app": False,
        }
    billing = get_org_billing(client, org_id) or {
        "plan_code": DEFAULT_PLAN_CODE,
        "billing_status": "trialing",
    }
    status = normalize_billing_status(billing.get("billing_status"))
    access = compute_app_access(status)
    return {
        "status": status,
        "plan_code": (billing.get("plan_code") or DEFAULT_PLAN_CODE).strip().lower(),
        "can_access_app": access["can_access_app"],
        "trial_ends_at": billing.get("current_period_end"),
    }


def _resolve_user_row(client, auth_user_id: str) -> dict:
    try:
        user_resp = (
            client.table("users")
            .select("id, org_id, email, full_name, avatar_url, role, created_at, updated_at")
            .eq("auth_user_id", auth_user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        if _is_missing_error(exc):
            return {}
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not user_resp.data:
        return {}
    return dict(user_resp.data[0])


@router.get("/me")
async def me(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """GET /api/auth/me — returns backwards-compatible + structured user payload."""
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    auth_user_id = current_user["user_id"]
    user_row = _resolve_user_row(client, auth_user_id)
    organizations = load_user_organizations(client, auth_user_id)
    resolved_org_id = org_id or pick_default_org_id(
        [org["id"] for org in organizations],
        primary_org_id=str(user_row.get("org_id")) if user_row.get("org_id") else load_user_primary_org_id(client, auth_user_id),
    )
    role = _resolve_role(client, resolved_org_id, auth_user_id)

    merged_user = {
        "id": auth_user_id,
        "email": user_row.get("email") or current_user.get("email"),
        "full_name": user_row.get("full_name"),
        "avatar_url": user_row.get("avatar_url"),
        "role": user_row.get("role") or role,
        "created_at": user_row.get("created_at"),
        "updated_at": user_row.get("updated_at"),
    }

    org_name_by_id = {org["id"]: org.get("name") for org in organizations}
    current_org = (
        {"id": resolved_org_id, "name": org_name_by_id.get(resolved_org_id) or "Current Organization"}
        if resolved_org_id
        else None
    )
    onboarding = _load_onboarding_summary(client, resolved_org_id)
    billing = _load_billing_summary(client, resolved_org_id)

    return {
        "user_id": auth_user_id,
        "org_id": resolved_org_id,
        "email": current_user.get("email"),
        "role": role,
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
async def update_me(
    body: UserProfileUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if not payload:
        return {"id": current_user["user_id"], "email": current_user.get("email")}

    update_resp = (
        client.table("users")
        .update(payload)
        .eq("auth_user_id", current_user["user_id"])
        .select("id, email, full_name, avatar_url, role, created_at, updated_at")
        .limit(1)
        .execute()
    )
    if _is_missing_error(update_resp.error):
        return {
            "id": current_user["user_id"],
            "email": current_user.get("email"),
            **payload,
        }
    if update_resp.error:
        raise HTTPException(status_code=500, detail=str(update_resp.error))
    row = (update_resp.data or [{}])[0]
    return dict(row)


@router.post("/change-password")
async def change_password(
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

    admin_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        admin_client.auth.admin.update_user_by_id(
            current_user["user_id"],
            {"password": body.new_password},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to change password: {exc}")
    return {"ok": True}


@router.get("/sessions")
async def list_sessions(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
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
                sessions.append(
                    {
                        "id": str(row.get("id") or ""),
                        "device": str(row.get("user_agent") or "Unknown device"),
                        "ip": str(row.get("ip") or "Unknown IP"),
                        "last_active": str(row.get("updated_at") or row.get("created_at") or ""),
                        "current": idx == 0,
                    }
                )
    except Exception:
        sessions = []

    if not sessions:
        user_agent = request.headers.get("user-agent") or "Current browser"
        ip = request.headers.get("x-forwarded-for") or request.client.host if request.client else "unknown"
        sessions = [
            {
                "id": "current",
                "device": user_agent,
                "ip": ip,
                "last_active": datetime.now(timezone.utc).isoformat(),
                "current": True,
            }
        ]
    return {"sessions": sessions}


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        client.schema("auth").table("sessions").delete().eq("id", session_id).eq(
            "user_id", current_user["user_id"]
        ).execute()
    except Exception:
        pass
    return {"ok": True}


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        client.schema("auth").table("sessions").delete().eq(
            "user_id", current_user["user_id"]
        ).execute()
    except Exception:
        pass
    return {"ok": True}


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

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        client.table("users").update({"avatar_url": avatar_data_url}).eq(
            "auth_user_id", current_user["user_id"]
        ).execute()
    except Exception:
        pass
    return {"avatar_url": avatar_data_url}
