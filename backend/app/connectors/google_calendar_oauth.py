"""Google Calendar OAuth2 + token lifecycle (STA-23; shared Gravitre OAuth app)."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.connectors.google_oauth_common import (
    GOOGLE_AUTHORIZE_URL,
    google_oauth_configured,
    google_oauth_credentials,
    google_oauth_redirect_uri,
)
from app.connectors.google_oauth_tokens import exchange_google_code, refresh_google_token
from app.connectors.hubspot_oauth import (
    _connector_environment,
    load_oauth_tokens,
    mark_connector_oauth_failure,
    mark_connector_oauth_success,
    store_oauth_tokens,
    token_needs_refresh,
)

logger = logging.getLogger(__name__)

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
TOKEN_REFRESH_BUFFER_SEC = 300


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"googlecalendar", "google_calendar", "calendar"}:
        return "google_calendar"
    return key


def google_calendar_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    return google_oauth_configured(settings, environment_name)


def google_calendar_redirect_uri(settings: Settings) -> str:
    return google_oauth_redirect_uri(settings, "google_calendar")


def google_calendar_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": CALENDAR_SCOPE,
            "redirect_uri": redirect_uri,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
    )
    return f"{GOOGLE_AUTHORIZE_URL}?{query}"


def refresh_google_calendar_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = google_oauth_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "Google OAuth is not configured on the server"
    if not settings.connector_secrets_encryption_key:
        return None, "Connector secrets encryption is not configured"

    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return None, "OAuth not completed"

    refresh_token = tokens.get("refresh_token")
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and refresh_token:
        try:
            tokens = refresh_google_token(
                str(refresh_token),
                client_id=client_id,
                client_secret=client_secret,
            )
            store_oauth_tokens(client, org_id, connector_id, tokens, settings)
            logger.info("google_calendar_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            return None, f"Token refresh failed: {exc}"

    return tokens, None


def ensure_google_calendar_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    tokens, err = refresh_google_calendar_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not tokens:
        return None, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    if not token:
        return None, "OAuth not completed"
    return token, None


def complete_google_calendar_oauth_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    code: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
    reconnect: bool = False,
) -> None:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = google_oauth_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("Google OAuth is not configured")

    tokens = exchange_google_code(
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=google_calendar_redirect_uri(settings),
    )
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
    config = dict((existing.data or [{}])[0].get("config") or {})
    config["oauth_provider"] = "google_calendar"
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def google_calendar_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not google_calendar_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and not tokens.get("refresh_token"):
        return "auth_expired"
    token, err = ensure_google_calendar_session(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not token:
        return "auth_expired"
    return "connected"
