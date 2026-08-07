"""Marketo REST client credentials token lifecycle (STA-64)."""
from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.connectors.hubspot_oauth import (
    _connector_environment,
    load_oauth_tokens,
    mark_connector_oauth_failure,
    mark_connector_oauth_success,
    store_oauth_tokens,
    token_needs_refresh,
)
from app.core.safe_dict import safe_normalize_stored_dict

logger = logging.getLogger(__name__)

TOKEN_REFRESH_BUFFER_SEC = 300


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"marketo", "adobemarketo"}:
        return "marketo"
    return key


def marketo_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    _ = environment_name
    client_id = (settings.marketo_client_id or "").strip()
    client_secret = (settings.marketo_client_secret or "").strip()
    return client_id, client_secret


def marketo_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = marketo_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def marketo_identity_base(munchkin_id: str) -> str:
    mid = munchkin_id.strip()
    if not mid:
        raise ValueError("munchkin_id is required")
    return f"https://{mid}.mktorest.com"


def marketo_token_url(munchkin_id: str) -> str:
    base = marketo_identity_base(munchkin_id)
    query = urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": "{CLIENT_ID}",
            "client_secret": "{CLIENT_SECRET}",
        }
    )
    return f"{base}/identity/oauth/token?{query}"


def get_connector_munchkin_id(connector: dict[str, Any]) -> str | None:
    config = connector.get("config") or {}
    mid = config.get("munchkin_id") or config.get("munchkinId")
    return str(mid).strip() if mid else None


def _token_payload_from_response(data: dict[str, Any]) -> dict[str, Any]:
    expires_in = int(data.get("expires_in") or 3600)
    now = int(time.time())
    return {
        "access_token": data.get("access_token"),
        "token_type": data.get("token_type") or "bearer",
        "scope": data.get("scope"),
        "expires_at": now + expires_in,
        "updated_at": now,
    }


def fetch_marketo_client_credentials_token(
    munchkin_id: str,
    *,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    base = marketo_identity_base(munchkin_id)
    params = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{base}/identity/oauth/token", params=params)
        response.raise_for_status()
        payload = response.json()
    if not payload.get("access_token"):
        raise ValueError("Marketo token response missing access_token")
    return _token_payload_from_response(payload)


def refresh_marketo_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = marketo_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "Marketo OAuth is not configured on the server"
    if not settings.connector_secrets_encryption_key:
        return None, "Connector secrets encryption is not configured"

    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        return None, "Connector not found"
    munchkin_id = get_connector_munchkin_id(dict(row.data[0]))
    if not munchkin_id:
        return None, "Marketo munchkin_id not configured on connector"

    tokens = load_oauth_tokens(client, connector_id, settings)
    if tokens and tokens.get("access_token") and not token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC):
        return tokens, None

    try:
        tokens = fetch_marketo_client_credentials_token(
            munchkin_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        store_oauth_tokens(client, org_id, connector_id, tokens, settings)
        logger.info("marketo_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
    except httpx.HTTPError as exc:
        mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
        return None, f"Token refresh failed: {exc}"

    return tokens, None


def ensure_marketo_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Return (access_token, munchkin_id, error)."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        return None, None, "Connector not found"
    munchkin_id = get_connector_munchkin_id(dict(row.data[0]))
    if not munchkin_id:
        return None, None, "Marketo munchkin_id not configured"

    tokens, err = refresh_marketo_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not tokens:
        return None, munchkin_id, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    if not token:
        return None, munchkin_id, "OAuth not completed"
    return token, munchkin_id, None


def complete_marketo_client_credentials_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    munchkin_id: str,
    environment_name: str | None = None,
    reconnect: bool = False,
) -> None:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = marketo_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("Marketo OAuth is not configured")

    mid = munchkin_id.strip()
    if not mid:
        raise ValueError("munchkin_id is required")

    tokens = fetch_marketo_client_credentials_token(mid, client_id=client_id, client_secret=client_secret)
    store_oauth_tokens(client, org_id, connector_id, tokens, settings)
    mark_connector_oauth_success(
        client,
        org_id,
        connector_id,
        tokens,
        environment_name=env,
        reconnect=reconnect,
    )

    existing = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((existing.data or [{}])[0], key="config")
    config["oauth_provider"] = "marketo"
    config["munchkin_id"] = mid
    config["auth_type"] = "client_credentials"
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def marketo_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not marketo_oauth_configured(settings, env):
        return "misconfigured"
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data or not get_connector_munchkin_id(dict(row.data[0])):
        return "pending_auth"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    _, _, err = ensure_marketo_session(client, org_id, connector_id, settings, environment_name=env)
    if err:
        return "auth_expired"
    return "connected"
