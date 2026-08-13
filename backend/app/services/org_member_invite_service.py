"""Shared org-member invite + membership attach helpers."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.config import Settings
from app.core.supabase_response import response_error
from app.public_urls import PRODUCTION_APP_URL

_ORG_MEMBER_ROLES = {"admin", "member", "viewer"}


def normalize_org_member_role(role: str | None, *, default: str = "member") -> str:
    normalized = str(role or default).strip().lower()
    if normalized not in _ORG_MEMBER_ROLES:
        return default
    return normalized


def _invite_redirect_url(settings: Settings) -> str:
    base = str(settings.public_app_url or "").strip().rstrip("/")
    if not base:
        base = PRODUCTION_APP_URL
    return f"{base}/auth/callback?next=/onboarding"


def _lookup_auth_user_id_by_email(client: Any, email: str) -> str | None:
    users = (
        client.table("users")
        .select("auth_user_id")
        .ilike("email", email)
        .limit(1)
        .execute()
    )
    if response_error(users):
        return None
    row = (users.data or [None])[0]
    if isinstance(row, dict) and row.get("auth_user_id"):
        return str(row["auth_user_id"])
    try:
        auth_users = (
            client.schema("auth")
            .table("users")
            .select("id")
            .ilike("email", email)
            .limit(1)
            .execute()
        )
    except Exception:  # noqa: BLE001
        return None
    if response_error(auth_users):
        return None
    auth_row = (auth_users.data or [None])[0]
    if isinstance(auth_row, dict) and auth_row.get("id"):
        return str(auth_row["id"])
    return None


def _extract_auth_user_id(invite_response: Any) -> str | None:
    user = getattr(invite_response, "user", None)
    if user is None and isinstance(invite_response, dict):
        user = invite_response.get("user")
    if user is None:
        return None
    uid = getattr(user, "id", None)
    if uid is None and isinstance(user, dict):
        uid = user.get("id")
    if uid is None:
        return None
    return str(uid)


def _already_registered_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "already" in msg and ("registered" in msg or "exists" in msg)


def invite_org_member_by_email(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    email: str,
    role: str,
    invited_by_user_id: str,
    send_invite: bool = True,
    invite_context: str = "org_member",
) -> dict[str, Any]:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    normalized_role = normalize_org_member_role(role)
    auth_user_id = _lookup_auth_user_id_by_email(client, normalized_email)
    invite_email_sent = False
    invite_email_status = "not_requested"

    if send_invite:
        invite_email_status = "sent"
        options = {
            "redirect_to": _invite_redirect_url(settings),
            "data": {
                "invited_org_id": org_id,
                "invited_role": normalized_role,
                "invite_context": invite_context,
                "invited_by": invited_by_user_id,
            },
        }
        try:
            invite_response = client.auth.admin.invite_user_by_email(normalized_email, options)
            invited_uid = _extract_auth_user_id(invite_response)
            if invited_uid:
                auth_user_id = invited_uid
            invite_email_sent = True
        except Exception as exc:  # noqa: BLE001
            if auth_user_id and _already_registered_error(exc):
                invite_email_status = "already_registered"
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Unable to send invite email: {exc}",
                ) from exc

    if not auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user account found for this email. Enable invite email to provision one.",
        )

    existing_member = (
        client.table("organization_members")
        .select("id")
        .eq("org_id", org_id)
        .eq("user_id", auth_user_id)
        .limit(1)
        .execute()
    )
    if response_error(existing_member):
        raise HTTPException(status_code=500, detail=str(response_error(existing_member)))
    membership_created = not bool(existing_member.data)

    upserted = (
        client.table("organization_members")
        .upsert(
            {
                "org_id": org_id,
                "user_id": auth_user_id,
                "role": normalized_role,
            },
            on_conflict="org_id,user_id",
        )
        .execute()
    )
    if response_error(upserted):
        raise HTTPException(status_code=500, detail=str(response_error(upserted)))

    return {
        "email": normalized_email,
        "user_id": auth_user_id,
        "role": normalized_role,
        "invite_email_sent": invite_email_sent,
        "invite_email_status": invite_email_status,
        "membership_created": membership_created,
    }
