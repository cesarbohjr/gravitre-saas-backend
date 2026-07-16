"""HubSpot OAuth2 + token lifecycle (STA-13 / STA-14)."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.config import Settings
from app.public_urls import connector_oauth_callback_url
from app.connectors.repository import get_decrypted_secret, set_secret

logger = logging.getLogger(__name__)

OAUTH_TOKEN_KEY = "oauth_tokens"
HUBSPOT_AUTHORIZE_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HUBSPOT_REQUIRED_SCOPES = (
    "crm.objects.contacts.read crm.objects.contacts.write "
    "crm.objects.deals.read crm.objects.deals.write "
    "crm.objects.companies.read crm.objects.tickets.write "
    "crm.objects.notes.write "
    "crm.lists.read crm.lists.write oauth"
)
HUBSPOT_OPTIONAL_SCOPES = (
    "automation crm.objects.companies.write crm.objects.owners.read crm.objects.tickets.read"
)
# Backward-compatible alias for callers/tests that expect a single scope string.
HUBSPOT_SCOPES = f"{HUBSPOT_REQUIRED_SCOPES} {HUBSPOT_OPTIONAL_SCOPES}".strip()
TOKEN_REFRESH_BUFFER_SEC = 300

_STAGING_ENVIRONMENTS = frozenset({"staging", "sandbox", "development", "dev", "test"})


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "")
    if key in {"hubspot", "hubspotcrm"}:
        return "hubspot"
    return key


def is_staging_environment(environment_name: str | None) -> bool:
    return (environment_name or "production").strip().lower() in _STAGING_ENVIRONMENTS


def hubspot_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    """Resolve HubSpot app credentials for production vs staging/sandbox."""
    if is_staging_environment(environment_name):
        client_id = (settings.hubspot_sandbox_client_id or settings.hubspot_client_id or "").strip()
        client_secret = (settings.hubspot_sandbox_client_secret or settings.hubspot_client_secret or "").strip()
    else:
        client_id = (settings.hubspot_client_id or "").strip()
        client_secret = (settings.hubspot_client_secret or "").strip()
    return client_id, client_secret


def hubspot_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = hubspot_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def hubspot_redirect_uri(settings: Settings) -> str:
    return connector_oauth_callback_url(
        public_app_url=settings.public_app_url,
        api_public_url=settings.api_public_url,
        vendor="hubspot",
    )


def hubspot_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    from urllib.parse import urlencode

    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": HUBSPOT_REQUIRED_SCOPES,
            "optional_scope": HUBSPOT_OPTIONAL_SCOPES,
            "state": state,
        }
    )
    return f"{HUBSPOT_AUTHORIZE_URL}?{query}"


def _token_payload_from_response(data: dict[str, Any]) -> dict[str, Any]:
    expires_in = int(data.get("expires_in") or 0)
    now = int(time.time())
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_at": now + expires_in if expires_in else None,
        "token_type": data.get("token_type") or "bearer",
        "updated_at": now,
    }


def exchange_hubspot_code(
    code: str,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            HUBSPOT_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return _token_payload_from_response(response.json())


def refresh_hubspot_token(
    refresh_token: str,
    *,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            HUBSPOT_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        payload = _token_payload_from_response(response.json())
        if not payload.get("refresh_token"):
            payload["refresh_token"] = refresh_token
        return payload


def load_oauth_tokens(client: Any, connector_id: str, settings: Settings) -> dict[str, Any] | None:
    raw = get_decrypted_secret(client, connector_id, OAUTH_TOKEN_KEY, settings)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def store_oauth_tokens(
    client: Any,
    org_id: str,
    connector_id: str,
    tokens: dict[str, Any],
    settings: Settings,
) -> None:
    set_secret(client, org_id, connector_id, OAUTH_TOKEN_KEY, json.dumps(tokens), settings)


def introspect_hubspot_access_token(access_token: str) -> dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        response = client.get(f"https://api.hubapi.com/oauth/v1/access-tokens/{access_token}")
        response.raise_for_status()
        return response.json()


def enrich_tokens_from_introspection(tokens: dict[str, Any], introspection: dict[str, Any]) -> dict[str, Any]:
    merged = dict(tokens)
    merged["hub_id"] = introspection.get("hub_id")
    merged["hub_domain"] = introspection.get("hub_domain")
    merged["user_id"] = introspection.get("user_id")
    merged["scopes"] = introspection.get("scopes") or []
    merged["app_id"] = introspection.get("app_id")
    if introspection.get("expires_in") is not None:
        merged["expires_at"] = int(time.time()) + int(introspection["expires_in"])
    return merged


def _connector_environment(client: Any, org_id: str, connector_id: str) -> str:
    row = (
        client.table("connectors")
        .select("environment")
        .eq("org_id", org_id)
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    if row.data:
        return str(row.data[0].get("environment") or "production")
    return "production"


def mark_connector_oauth_failure(
    client: Any,
    org_id: str,
    connector_id: str,
    error: str,
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
    config["oauth_error"] = error[:500]
    config["oauth_error_at"] = int(time.time())
    client.table("connectors").update({"status": "error", "config": config}).eq("id", connector_id).eq(
        "org_id", org_id
    ).execute()


def mark_connector_oauth_success(
    client: Any,
    org_id: str,
    connector_id: str,
    tokens: dict[str, Any],
    *,
    environment_name: str | None = None,
    reconnect: bool = False,
) -> None:
    existing = (
        client.table("connectors")
        .select("config, environment")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    row = (existing.data or [{}])[0]
    config = dict(row.get("config") or {})
    env = environment_name or row.get("environment") or "production"
    config.update(
        {
            "auth_type": "oauth",
            "oauth_provider": "hubspot",
            "oauth_connected_at": int(time.time()),
            "oauth_environment": env,
            "hub_id": tokens.get("hub_id"),
            "hub_domain": tokens.get("hub_domain"),
        }
    )
    config.pop("oauth_error", None)
    config.pop("oauth_error_at", None)
    if reconnect:
        config["oauth_reconnected_at"] = int(time.time())
    client.table("connectors").update({"status": "active", "config": config}).eq("id", connector_id).eq(
        "org_id", org_id
    ).execute()


def token_needs_refresh(tokens: dict[str, Any], buffer_sec: int = TOKEN_REFRESH_BUFFER_SEC) -> bool:
    expires_at = tokens.get("expires_at")
    if not expires_at:
        return False
    return float(expires_at) - buffer_sec < time.time()


def refresh_hubspot_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Refresh tokens when within buffer window. Returns (tokens, error)."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = hubspot_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "HubSpot OAuth is not configured on the server"
    if not settings.connector_secrets_encryption_key:
        return None, "Connector secrets encryption is not configured"

    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return None, "OAuth not completed"

    refresh_token = tokens.get("refresh_token")
    if token_needs_refresh(tokens) and refresh_token:
        try:
            tokens = refresh_hubspot_token(
                str(refresh_token),
                client_id=client_id,
                client_secret=client_secret,
            )
            store_oauth_tokens(client, org_id, connector_id, tokens, settings)
            logger.info("hubspot_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            return None, f"Token refresh failed: {exc}"

    return tokens, None


def complete_hubspot_oauth_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    code: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
    reconnect: bool = False,
) -> None:
    """Exchange OAuth code, introspect, persist encrypted tokens, update connector row."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = hubspot_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("HubSpot OAuth is not configured")

    tokens = exchange_hubspot_code(
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=hubspot_redirect_uri(settings),
    )
    access = str(tokens.get("access_token") or "")
    introspection = introspect_hubspot_access_token(access)
    tokens = enrich_tokens_from_introspection(tokens, introspection)
    store_oauth_tokens(client, org_id, connector_id, tokens, settings)
    mark_connector_oauth_success(
        client, org_id, connector_id, tokens, environment_name=env, reconnect=reconnect
    )
    from app.services.hubspot_trigger_service import on_hubspot_connector_connected

    on_hubspot_connector_connected(client, org_id, connector_id, settings)


def ensure_hubspot_access_token(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
    validate_remote: bool = True,
) -> tuple[str | None, str | None]:
    """Return (access_token, error). Refreshes when near expiry; optional HubSpot introspection."""
    tokens, err = refresh_hubspot_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=environment_name
    )
    if err or not tokens:
        return None, err or "OAuth not completed"

    access = str(tokens.get("access_token") or "")
    if not validate_remote:
        return access, None

    try:
        introspection = introspect_hubspot_access_token(access)
        enriched = enrich_tokens_from_introspection(tokens, introspection)
        if enriched != tokens:
            store_oauth_tokens(client, org_id, connector_id, enriched, settings)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token expired or revoked")
            return None, "Token expired or revoked"
        return None, "Token validation failed"
    except httpx.HTTPError:
        return None, "Token validation failed"
    return access, None


def hubspot_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
    validate_remote: bool = False,
) -> str:
    """connected | pending_auth | auth_expired | misconfigured"""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not hubspot_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    if token_needs_refresh(tokens) and not tokens.get("refresh_token"):
        return "auth_expired"
    _, err = ensure_hubspot_access_token(
        client,
        org_id,
        connector_id,
        settings,
        environment_name=env,
        validate_remote=validate_remote,
    )
    if err:
        return "auth_expired"
    return "connected"
