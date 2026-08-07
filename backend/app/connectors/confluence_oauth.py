"""Confluence Cloud OAuth 2.0 (3LO) + token lifecycle (STA-44)."""
from __future__ import annotations

import logging
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
from app.connectors.jira_oauth import (
    JIRA_AUTHORIZE_URL,
    exchange_jira_code,
    fetch_accessible_jira_sites,
    refresh_jira_token,
)
from app.core.safe_dict import safe_normalize_stored_dict

logger = logging.getLogger(__name__)

CONFLUENCE_SCOPES = (
    "read:confluence-content.all read:confluence-space.summary offline_access"
)
TOKEN_REFRESH_BUFFER_SEC = 300


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"confluence", "confluencecloud", "atlassianconfluence"}:
        return "confluence"
    return key


def confluence_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    """Reuse Jira Atlassian app credentials when Confluence-specific vars are unset."""
    _ = environment_name
    client_id = (getattr(settings, "confluence_client_id", None) or settings.jira_client_id or "").strip()
    client_secret = (
        getattr(settings, "confluence_client_secret", None) or settings.jira_client_secret or ""
    ).strip()
    return client_id, client_secret


def confluence_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = confluence_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def confluence_redirect_uri(settings: Settings) -> str:
    return connector_oauth_callback_url(
        public_app_url=settings.public_app_url,
        api_public_url=settings.api_public_url,
        vendor="confluence",
    )


def confluence_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "audience": "api.atlassian.com",
            "client_id": client_id,
            "scope": CONFLUENCE_SCOPES,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
    )
    return f"{JIRA_AUTHORIZE_URL}?{query}"


def confluence_api_base_url(*, cloud_id: str) -> str:
    return f"https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/api/v2"


def pick_confluence_cloud_site(sites: list[dict[str, Any]]) -> dict[str, Any] | None:
    for site in sites:
        scopes = site.get("scopes") or []
        scope_text = " ".join(scopes) if isinstance(scopes, list) else str(scopes)
        lowered = scope_text.lower()
        if "confluence" in lowered:
            return site
    return sites[0] if sites else None


def refresh_confluence_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = confluence_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "Confluence OAuth is not configured on the server"
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
            logger.info("confluence_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
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
    config = safe_normalize_stored_dict((row.data or [{}])[0], key="config")
    cloud_id = (config.get("cloud_id") or config.get("cloudId") or "").strip()
    return cloud_id or None


def ensure_confluence_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Return (access_token, cloud_id, error)."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    tokens, err = refresh_confluence_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not tokens:
        return None, None, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    cloud_id = _connector_cloud_id(client, org_id, connector_id)
    if not token:
        return None, None, "OAuth not completed"
    if not cloud_id:
        return None, None, "Confluence cloud_id missing; reconnect OAuth"
    return token, cloud_id, None


def complete_confluence_oauth_connection(
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
    client_id, client_secret = confluence_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("Confluence OAuth is not configured")

    tokens = exchange_jira_code(
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=confluence_redirect_uri(settings),
    )
    access_token = str(tokens.get("access_token") or "")
    if not access_token:
        raise ValueError("Confluence token exchange did not return access_token")

    sites = fetch_accessible_jira_sites(access_token)
    site = pick_confluence_cloud_site(sites)
    if not site or not site.get("id"):
        raise ValueError("No accessible Confluence Cloud site found for this account")

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
    config["oauth_provider"] = "confluence"
    config["cloud_id"] = str(site["id"])
    if site.get("url"):
        config["site_url"] = site["url"]
    if site.get("name"):
        config["site_name"] = site["name"]
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def confluence_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not confluence_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and not tokens.get("refresh_token"):
        return "auth_expired"
    _, _, err = ensure_confluence_session(client, org_id, connector_id, settings, environment_name=env)
    if err:
        return "auth_expired"
    return "connected"
