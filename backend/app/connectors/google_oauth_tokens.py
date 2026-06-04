"""Google OAuth2 token exchange + refresh (shared by GA4, Calendar, etc.)."""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.connectors.google_oauth_common import GOOGLE_TOKEN_URL


def token_payload_from_response(data: dict[str, Any]) -> dict[str, Any]:
    expires_in = int(data.get("expires_in") or 3600)
    now = int(time.time())
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "token_type": data.get("token_type") or "Bearer",
        "scope": data.get("scope"),
        "expires_at": now + expires_in,
        "updated_at": now,
    }


def token_request(*, client_id: str, client_secret: str, body: dict[str, str]) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            GOOGLE_TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return token_payload_from_response(response.json())


def exchange_google_code(
    code: str,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    return token_request(
        client_id=client_id,
        client_secret=client_secret,
        body={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )


def refresh_google_token(
    refresh_token: str,
    *,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    payload = token_request(
        client_id=client_id,
        client_secret=client_secret,
        body={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    if not payload.get("refresh_token"):
        payload["refresh_token"] = refresh_token
    return payload
