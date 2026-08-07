"""QuickBooks Online OAuth2 + token lifecycle (STA-33)."""
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

QUICKBOOKS_SCOPE = "com.intuit.quickbooks.accounting"
QUICKBOOKS_AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
QUICKBOOKS_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
TOKEN_REFRESH_BUFFER_SEC = 300

_STAGING_ENVIRONMENTS = frozenset({"staging", "sandbox", "development", "dev", "test"})


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"quickbooks", "qbo", "quickbooksonline", "intuit"}:
        return "quickbooks"
    return key


def is_staging_environment(environment_name: str | None) -> bool:
    return (environment_name or "production").strip().lower() in _STAGING_ENVIRONMENTS


def quickbooks_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    if is_staging_environment(environment_name):
        client_id = (settings.quickbooks_sandbox_client_id or settings.quickbooks_client_id or "").strip()
        client_secret = (
            settings.quickbooks_sandbox_client_secret or settings.quickbooks_client_secret or ""
        ).strip()
    else:
        client_id = (settings.quickbooks_client_id or "").strip()
        client_secret = (settings.quickbooks_client_secret or "").strip()
    return client_id, client_secret


def quickbooks_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = quickbooks_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def quickbooks_redirect_uri(settings: Settings) -> str:
    return connector_oauth_callback_url(
        public_app_url=settings.public_app_url,
        api_public_url=settings.api_public_url,
        vendor="quickbooks",
    )


def quickbooks_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    *,
    environment_name: str | None = None,
) -> str:
    _ = environment_name
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": QUICKBOOKS_SCOPE,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{QUICKBOOKS_AUTHORIZE_URL}?{query}"


def quickbooks_api_base_url(*, realm_id: str, environment_name: str | None = None) -> str:
    host = (
        "sandbox-quickbooks.api.intuit.com"
        if is_staging_environment(environment_name)
        else "quickbooks.api.intuit.com"
    )
    return f"https://{host}/v3/company/{realm_id}"


def _token_payload_from_response(data: dict[str, Any]) -> dict[str, Any]:
    expires_in = int(data.get("expires_in") or 3600)
    now = int(time.time())
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "token_type": data.get("token_type") or "bearer",
        "expires_at": now + expires_in,
        "x_refresh_token_expires_in": data.get("x_refresh_token_expires_in"),
        "updated_at": now,
    }


def _token_request(
    *,
    client_id: str,
    client_secret: str,
    body: dict[str, str],
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            QUICKBOOKS_TOKEN_URL,
            data=body,
            auth=(client_id, client_secret),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return _token_payload_from_response(response.json())


def exchange_quickbooks_code(
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


def refresh_quickbooks_token(
    refresh_token: str,
    *,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    payload = _token_request(
        client_id=client_id,
        client_secret=client_secret,
        body={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    if not payload.get("refresh_token"):
        payload["refresh_token"] = refresh_token
    return payload


def refresh_quickbooks_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = quickbooks_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "QuickBooks OAuth is not configured on the server"
    if not settings.connector_secrets_encryption_key:
        return None, "Connector secrets encryption is not configured"

    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return None, "OAuth not completed"

    refresh_token = tokens.get("refresh_token")
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and refresh_token:
        try:
            tokens = refresh_quickbooks_token(
                str(refresh_token),
                client_id=client_id,
                client_secret=client_secret,
            )
            store_oauth_tokens(client, org_id, connector_id, tokens, settings)
            logger.info("quickbooks_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            return None, f"Token refresh failed: {exc}"

    return tokens, None


def _connector_realm_id(client: Any, org_id: str, connector_id: str) -> str | None:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((row.data or [{}])[0], key="config")
    realm_id = (config.get("realm_id") or config.get("realmId") or "").strip()
    return realm_id or None


def ensure_quickbooks_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (access_token, realm_id, api_base_url, error)."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    tokens, err = refresh_quickbooks_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not tokens:
        return None, None, None, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    realm_id = _connector_realm_id(client, org_id, connector_id)
    if not token:
        return None, None, None, "OAuth not completed"
    if not realm_id:
        return None, None, None, "QuickBooks realm_id missing; reconnect OAuth"
    return token, realm_id, quickbooks_api_base_url(realm_id=realm_id, environment_name=env), None


def complete_quickbooks_oauth_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    code: str,
    settings: Settings,
    *,
    realm_id: str | None = None,
    environment_name: str | None = None,
    reconnect: bool = False,
) -> None:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = quickbooks_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("QuickBooks OAuth is not configured")
    if not realm_id:
        raise ValueError("QuickBooks realmId is required from OAuth callback")

    tokens = exchange_quickbooks_code(
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=quickbooks_redirect_uri(settings),
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
    config = safe_normalize_stored_dict((existing.data or [{}])[0], key="config")
    config["oauth_provider"] = "quickbooks"
    config["realm_id"] = str(realm_id)
    config["sandbox"] = is_staging_environment(env)
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def quickbooks_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not quickbooks_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and not tokens.get("refresh_token"):
        return "auth_expired"
    _, _, _, err = ensure_quickbooks_session(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err:
        return "auth_expired"
    return "connected"
