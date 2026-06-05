"""Google Analytics (GA4) OAuth2 + property linking (STA-40)."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.connectors.google_analytics import list_ga4_properties
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

GA4_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
TOKEN_REFRESH_BUFFER_SEC = 300


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"googleanalytics", "google_analytics", "ga4", "ga"}:
        return "google_analytics"
    return key


def google_analytics_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    return google_oauth_credentials(settings, environment_name)


def google_analytics_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    return google_oauth_configured(settings, environment_name)


def google_analytics_redirect_uri(settings: Settings) -> str:
    return google_oauth_redirect_uri(settings, "google_analytics")


def google_analytics_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": GA4_READONLY_SCOPE,
            "redirect_uri": redirect_uri,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
    )
    return f"{GOOGLE_AUTHORIZE_URL}?{query}"


def refresh_google_analytics_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = google_analytics_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "Google Analytics OAuth is not configured on the server"
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
            logger.info(
                "google_analytics_token_refreshed org_id=%s connector_id=%s", org_id, connector_id
            )
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            return None, f"Token refresh failed: {exc}"

    return tokens, None


def ensure_google_analytics_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None]:
    """Return (access_token, error_message)."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    tokens, err = refresh_google_analytics_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not tokens:
        return None, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    if not token:
        return None, "OAuth not completed"
    return token, None


def _connector_property_id(client: Any, org_id: str, connector_id: str) -> str | None:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = dict((row.data or [{}])[0].get("config") or {})
    property_id = (config.get("property_id") or config.get("propertyId") or "").strip()
    return property_id or None


def _apply_property_link(
    client: Any,
    org_id: str,
    connector_id: str,
    *,
    property_id: str,
    property_name: str | None = None,
    property_resource: str | None = None,
) -> None:
    existing = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = dict((existing.data or [{}])[0].get("config") or {})
    config["property_id"] = property_id
    if property_name:
        config["property_name"] = property_name
    if property_resource:
        config["property_resource"] = property_resource
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def link_ga4_property(
    client: Any,
    org_id: str,
    connector_id: str,
    *,
    property_id: str,
    property_name: str | None = None,
    property_resource: str | None = None,
) -> None:
    pid = property_id.strip()
    if not pid:
        raise ValueError("property_id is required")
    resource = property_resource or f"properties/{pid}"
    _apply_property_link(
        client,
        org_id,
        connector_id,
        property_id=pid,
        property_name=property_name,
        property_resource=resource,
    )


def complete_google_analytics_oauth_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    code: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
    reconnect: bool = False,
) -> bool:
    """Complete OAuth. Returns True when exactly one GA4 property was auto-linked."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = google_analytics_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("Google Analytics OAuth is not configured")

    tokens = exchange_google_analytics_code(
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=google_analytics_redirect_uri(settings),
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
    config["oauth_provider"] = "google_analytics"
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()

    access = str(tokens.get("access_token") or "")
    if not access:
        return False

    properties = list_ga4_properties(access)
    ga4_only = [p for p in properties if p.get("property_type") in {None, "PROPERTY_TYPE_ORDINARY", "PROPERTY_TYPE_UNSPECIFIED"}]
    candidates = ga4_only or properties
    if len(candidates) == 1:
        prop = candidates[0]
        link_ga4_property(
            client,
            org_id,
            connector_id,
            property_id=str(prop["property_id"]),
            property_name=prop.get("display_name"),
            property_resource=prop.get("property_resource"),
        )
        _ensure_marketing_workflow_after_ga4_connect(client, org_id, settings)
        return True
    _ensure_marketing_workflow_after_ga4_connect(client, org_id, settings)
    return False


def _ensure_marketing_workflow_after_ga4_connect(
    client: Any,
    org_id: str,
    settings: Settings,
) -> None:
    from app.services.marketing_workflow_service import on_marketing_connectors_updated

    on_marketing_connectors_updated(client, org_id, settings)


def google_analytics_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not google_analytics_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and not tokens.get("refresh_token"):
        return "auth_expired"
    token, err = ensure_google_analytics_session(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not token:
        return "auth_expired"
    if not _connector_property_id(client, org_id, connector_id):
        return "pending_property"
    return "connected"
