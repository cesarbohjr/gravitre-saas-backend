"""NetSuite OAuth2 + token lifecycle (STA-56)."""
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

NETSUITE_SCOPE = "rest_webservices"
TOKEN_REFRESH_BUFFER_SEC = 300

_STAGING_ENVIRONMENTS = frozenset({"staging", "sandbox", "development", "dev", "test"})


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"netsuite", "netsuiteerp", "oracleerp"}:
        return "netsuite"
    return key


def is_staging_environment(environment_name: str | None) -> bool:
    return (environment_name or "production").strip().lower() in _STAGING_ENVIRONMENTS


def netsuite_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    if is_staging_environment(environment_name):
        client_id = (settings.netsuite_sandbox_client_id or settings.netsuite_client_id or "").strip()
        client_secret = (
            settings.netsuite_sandbox_client_secret or settings.netsuite_client_secret or ""
        ).strip()
    else:
        client_id = (settings.netsuite_client_id or "").strip()
        client_secret = (settings.netsuite_client_secret or "").strip()
    return client_id, client_secret


def netsuite_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = netsuite_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def netsuite_redirect_uri(settings: Settings) -> str:
    return connector_oauth_callback_url(
        public_app_url=settings.public_app_url,
        api_public_url=settings.api_public_url,
        vendor="netsuite",
    )


def _normalize_account_id(account_id: str) -> str:
    raw = account_id.strip().replace("-", "_")
    if "_" in raw:
        base, suffix = raw.rsplit("_", 1)
        return f"{base}_{suffix.upper()}"
    return raw


def netsuite_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    *,
    account_id: str,
    environment_name: str | None = None,
) -> str:
    _ = environment_name
    acct = _normalize_account_id(account_id)
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": NETSUITE_SCOPE,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"https://{acct}.app.netsuite.com/app/login/oauth2/authorize.nl?{query}"


def netsuite_token_url(account_id: str) -> str:
    acct = _normalize_account_id(account_id)
    return f"https://{acct}.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token"


def netsuite_api_base_url(*, account_id: str, environment_name: str | None = None) -> str:
    _ = environment_name
    acct = _normalize_account_id(account_id)
    return f"https://{acct}.suitetalk.api.netsuite.com/services/rest/record/v1"


def _token_payload_from_response(data: dict[str, Any]) -> dict[str, Any]:
    expires_in = int(data.get("expires_in") or 3600)
    now = int(time.time())
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "token_type": data.get("token_type") or "bearer",
        "expires_at": now + expires_in,
        "updated_at": now,
    }


def _token_request(
    *,
    account_id: str,
    client_id: str,
    client_secret: str,
    body: dict[str, str],
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            netsuite_token_url(account_id),
            data=body,
            auth=(client_id, client_secret),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return _token_payload_from_response(response.json())


def exchange_netsuite_code(
    code: str,
    *,
    account_id: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    return _token_request(
        account_id=account_id,
        client_id=client_id,
        client_secret=client_secret,
        body={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )


def refresh_netsuite_token(
    refresh_token: str,
    *,
    account_id: str,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    payload = _token_request(
        account_id=account_id,
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


def refresh_netsuite_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = netsuite_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "NetSuite OAuth is not configured on the server"
    if not settings.connector_secrets_encryption_key:
        return None, "Connector secrets encryption is not configured"

    account_id = _connector_account_id(client, org_id, connector_id)
    if not account_id:
        return None, "NetSuite account_id missing; reconnect OAuth"

    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return None, "OAuth not completed"

    refresh_token = tokens.get("refresh_token")
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and refresh_token:
        try:
            tokens = refresh_netsuite_token(
                str(refresh_token),
                account_id=account_id,
                client_id=client_id,
                client_secret=client_secret,
            )
            store_oauth_tokens(client, org_id, connector_id, tokens, settings)
            logger.info("netsuite_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            return None, f"Token refresh failed: {exc}"

    return tokens, None


def _connector_account_id(client: Any, org_id: str, connector_id: str) -> str | None:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((row.data or [{}])[0], key="config")
    account_id = (config.get("account_id") or config.get("accountId") or "").strip()
    return account_id or None


def ensure_netsuite_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (access_token, account_id, api_base_url, error)."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    tokens, err = refresh_netsuite_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not tokens:
        return None, None, None, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    account_id = _connector_account_id(client, org_id, connector_id)
    if not token:
        return None, None, None, "OAuth not completed"
    if not account_id:
        return None, None, None, "NetSuite account_id missing; reconnect OAuth"
    return (
        token,
        account_id,
        netsuite_api_base_url(account_id=account_id, environment_name=env),
        None,
    )


def complete_netsuite_oauth_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    code: str,
    settings: Settings,
    *,
    account_id: str | None = None,
    environment_name: str | None = None,
    reconnect: bool = False,
) -> None:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = netsuite_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("NetSuite OAuth is not configured")

    existing = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((existing.data or [{}])[0], key="config")
    resolved_account_id = (account_id or config.get("account_id") or config.get("accountId") or "").strip()
    if not resolved_account_id:
        raise ValueError("NetSuite accountId is required from OAuth callback or connector config")

    tokens = exchange_netsuite_code(
        code,
        account_id=resolved_account_id,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=netsuite_redirect_uri(settings),
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
    config["oauth_provider"] = "netsuite"
    config["account_id"] = _normalize_account_id(resolved_account_id)
    config["sandbox"] = is_staging_environment(env)
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def netsuite_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not netsuite_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and not tokens.get("refresh_token"):
        return "auth_expired"
    _, _, _, err = ensure_netsuite_session(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err:
        return "auth_expired"
    return "connected"
