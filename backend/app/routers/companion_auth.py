"""Sessions for the desktop app and the browser extension.

The companions used to receive a copy of the web session's access token, which
expires after an hour, and they had no way to renew it. Sharing the web refresh
token is not an option either: Supabase rotates refresh tokens, so two clients
spending the same one would revoke each other.

``POST /api/auth/companion-session`` mints a separate Supabase session for the
signed-in user (magic-link token minted and verified server-side, no email is
sent). ``POST /api/auth/companion-refresh`` renews it. Each companion therefore
owns its own refresh-token family and signing out of one never signs out the
others.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class CompanionSessionRequest(BaseModel):
    client: Literal["desktop", "extension"]


class CompanionRefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=8, max_length=512)


def _auth_base(settings: Settings) -> str:
    return f"{settings.supabase_url_stripped}/auth/v1"


def _session_payload(body: dict[str, Any]) -> dict[str, Any]:
    access_token = str(body.get("access_token") or "")
    refresh_token = str(body.get("refresh_token") or "")
    if not access_token or not refresh_token:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Sign-in service returned no session")
    user = body.get("user") if isinstance(body.get("user"), dict) else {}
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": body.get("expires_in"),
        "expires_at": body.get("expires_at"),
        "user_id": user.get("id"),
    }


def _mint_session(settings: Settings, *, email: str) -> dict[str, Any]:
    base = _auth_base(settings)
    service = settings.supabase_service_role_key
    with httpx.Client(timeout=_TIMEOUT) as client:
        link = client.post(
            f"{base}/admin/generate_link",
            headers={"apikey": service, "Authorization": f"Bearer {service}"},
            json={"type": "magiclink", "email": email},
        )
        if link.status_code >= 400:
            logger.warning("companion_session generate_link failed status=%s", link.status_code)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not start a session")
        link_body = link.json()
        props = link_body.get("properties") if isinstance(link_body.get("properties"), dict) else link_body
        token_hash = str((props or {}).get("hashed_token") or "")
        if not token_hash:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not start a session")
        verified = client.post(
            f"{base}/verify",
            headers={"apikey": settings.supabase_anon_key},
            json={"type": "magiclink", "token_hash": token_hash},
        )
        if verified.status_code >= 400:
            logger.warning("companion_session verify failed status=%s", verified.status_code)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not start a session")
        return verified.json()


@router.post("/companion-session")
def create_companion_session(
    body: CompanionSessionRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """New, independent session for the caller, for the desktop app or the extension."""
    email = str(current_user.get("email") or "").strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has no email address, so a desktop session can't be created",
        )
    session = _session_payload(_mint_session(settings, email=email))
    # Defense in depth: the minted session must belong to the caller.
    if session.get("user_id") and str(session["user_id"]) != str(current_user.get("user_id")):
        logger.error("companion_session user mismatch client=%s", body.client)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session does not match the signed-in user")
    logger.info("companion_session issued client=%s user_id=%s", body.client, current_user.get("user_id"))
    return session


@router.post("/companion-refresh")
def refresh_companion_session(
    body: CompanionRefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Renew a companion session. The refresh token is the credential."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        res = client.post(
            f"{_auth_base(settings)}/token",
            params={"grant_type": "refresh_token"},
            headers={"apikey": settings.supabase_anon_key},
            json={"refresh_token": body.refresh_token},
        )
    if res.status_code in (400, 401, 403):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Sign in again.")
    if res.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Sign-in service unavailable")
    return _session_payload(res.json())
