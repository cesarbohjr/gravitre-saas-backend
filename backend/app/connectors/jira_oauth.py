"""Jira Cloud OAuth 2.0 (3LO) + token lifecycle (STA-36)."""
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

logger = logging.getLogger(__name__)

JIRA_SCOPES = "read:jira-work write:jira-work offline_access"
JIRA_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
JIRA_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
JIRA_ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
TOKEN_REFRESH_BUFFER_SEC = 300


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"jira", "jiracloud", "atlassianjira"}:
        return "jira"
    return key


def jira_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    _ = environment_name
    client_id = (settings.jira_client_id or "").strip()
    client_secret = (settings.jira_client_secret or "").strip()
    return client_id, client_secret


def jira_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = jira_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def jira_redirect_uri(settings: Settings) -> str:
    return connector_oauth_callback_url(
        public_app_url=settings.public_app_url,
        api_public_url=settings.api_public_url,
        vendor="jira",
    )


def jira_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "audience": "api.atlassian.com",
            "client_id": client_id,
            "scope": JIRA_SCOPES,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
    )
    return f"{JIRA_AUTHORIZE_URL}?{query}"


def jira_api_base_url(*, cloud_id: str) -> str:
    return f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"


def _token_payload_from_response(data: dict[str, Any]) -> dict[str, Any]:
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


def _token_request(*, client_id: str, client_secret: str, body: dict[str, str]) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            JIRA_TOKEN_URL,
            json=body,
            auth=(client_id, client_secret),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return _token_payload_from_response(response.json())


def exchange_jira_code(
    code: str,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    return _token_request(
        client_id=client_id,
        client_secret=client_secret,
        body={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )


def refresh_jira_token(
    refresh_token: str,
    *,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    payload = _token_request(
        client_id=client_id,
        client_secret=client_secret,
        body={"grant_type": "refresh_token", "refresh_token": refresh_token},
    )
    if not payload.get("refresh_token"):
        payload["refresh_token"] = refresh_token
    return payload


def fetch_accessible_jira_sites(access_token: str) -> list[dict[str, Any]]:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            JIRA_ACCESSIBLE_RESOURCES_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, list):
        return []
    return [dict(item) for item in data if isinstance(item, dict)]


def pick_jira_cloud_site(sites: list[dict[str, Any]]) -> dict[str, Any] | None:
    for site in sites:
        scopes = site.get("scopes") or []
        scope_text = " ".join(scopes) if isinstance(scopes, list) else str(scopes)
        if "jira-work" in scope_text.lower() or "jira" in scope_text.lower():
            return site
    return sites[0] if sites else None


def refresh_jira_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = jira_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "Jira OAuth is not configured on the server"
    if not settings.connector_secrets_encryption_key:
        return None, "Connector secrets encryption is not configured"

    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return None, "OAuth not completed"

    refresh_token = tokens.get("refresh_token")
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and refresh_token:
        try:
            tokens = refresh_jira_token(
                str(refresh_token),
                client_id=client_id,
                client_secret=client_secret,
            )
            store_oauth_tokens(client, org_id, connector_id, tokens, settings)
            logger.info("jira_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            return None, f"Token refresh failed: {exc}"

    return tokens, None


def _connector_cloud_id(client: Any, org_id: str, connector_id: str) -> str | None:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = dict((row.data or [{}])[0].get("config") or {})
    cloud_id = (config.get("cloud_id") or config.get("cloudId") or "").strip()
    return cloud_id or None


def ensure_jira_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Return (access_token, cloud_id, error)."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    tokens, err = refresh_jira_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not tokens:
        return None, None, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    cloud_id = _connector_cloud_id(client, org_id, connector_id)
    if not token:
        return None, None, "OAuth not completed"
    if not cloud_id:
        return None, None, "Jira cloud_id missing; reconnect OAuth"
    return token, cloud_id, None


def complete_jira_oauth_connection(
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
    client_id, client_secret = jira_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("Jira OAuth is not configured")

    tokens = exchange_jira_code(
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=jira_redirect_uri(settings),
    )
    access_token = str(tokens.get("access_token") or "")
    if not access_token:
        raise ValueError("Jira token exchange did not return access_token")

    sites = fetch_accessible_jira_sites(access_token)
    site = pick_jira_cloud_site(sites)
    if not site or not site.get("id"):
        raise ValueError("No accessible Jira Cloud site found for this account")

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
    config["oauth_provider"] = "jira"
    config["cloud_id"] = str(site["id"])
    if site.get("url"):
        config["site_url"] = site["url"]
    if site.get("name"):
        config["site_name"] = site["name"]
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def jira_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not jira_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and not tokens.get("refresh_token"):
        return "auth_expired"
    _, _, err = ensure_jira_session(client, org_id, connector_id, settings, environment_name=env)
    if err:
        return "auth_expired"
    return "connected"
