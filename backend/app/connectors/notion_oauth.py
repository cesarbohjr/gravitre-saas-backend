"""Notion OAuth 2.0 + token storage (STA-43)."""
from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.public_urls import connector_oauth_callback_url
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

NOTION_AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
TOKEN_REFRESH_BUFFER_SEC = 300


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key == "notion":
        return "notion"
    return key


def notion_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    _ = environment_name
    return (settings.notion_client_id or "").strip(), (settings.notion_client_secret or "").strip()


def notion_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = notion_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def notion_redirect_uri(settings: Settings) -> str:
    return connector_oauth_callback_url(
        public_app_url=settings.public_app_url,
        api_public_url=settings.api_public_url,
        vendor="notion",
    )


def notion_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "owner": "user",
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{NOTION_AUTHORIZE_URL}?{query}"


def _token_payload_from_response(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "access_token": data.get("access_token"),
        "token_type": data.get("token_type") or "bearer",
        "bot_id": data.get("bot_id"),
        "workspace_id": data.get("workspace_id"),
        "workspace_name": data.get("workspace_name"),
        "workspace_icon": data.get("workspace_icon"),
        "duplicated_template_id": data.get("duplicated_template_id"),
        "owner": data.get("owner"),
        "updated_at": int(time.time()),
    }


def exchange_notion_code(
    code: str,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            NOTION_TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            auth=(client_id, client_secret),
        )
        response.raise_for_status()
        return _token_payload_from_response(response.json())


def ensure_notion_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None]:
    """Return (access_token, error_message). Notion tokens do not refresh."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return None, "Notion OAuth not connected"
    access = str(tokens.get("access_token") or "").strip()
    if not access:
        return None, "Notion access token missing"
    return access, None


def complete_notion_oauth_connection(
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
    client_id, client_secret = notion_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("Notion OAuth is not configured")

    tokens = exchange_notion_code(
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=notion_redirect_uri(settings),
    )
    if not tokens.get("access_token"):
        raise ValueError("Notion token exchange did not return access_token")

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
    config["oauth_provider"] = "notion"
    if tokens.get("workspace_id"):
        config["notion_workspace_id"] = str(tokens["workspace_id"])
    if tokens.get("workspace_name"):
        config["notion_workspace_name"] = str(tokens["workspace_name"])
    if tokens.get("bot_id"):
        config["notion_bot_id"] = str(tokens["bot_id"])
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def notion_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not notion_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return "pending_auth"
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and not tokens.get("refresh_token"):
        # Notion integrations typically do not expire; treat missing token as expired only if empty
        if not str(tokens.get("access_token") or "").strip():
            return "auth_expired"
    token, err = ensure_notion_session(client, org_id, connector_id, settings, environment_name=env)
    if err or not token:
        return "auth_expired"
    return "connected"
