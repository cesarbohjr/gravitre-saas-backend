"""Salesforce OAuth2 + token lifecycle (STA-30)."""
from __future__ import annotations

import json
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.connectors.hubspot_oauth import (
    OAUTH_TOKEN_KEY,
    _connector_environment,
    load_oauth_tokens,
    mark_connector_oauth_failure,
    mark_connector_oauth_success,
    store_oauth_tokens,
    token_needs_refresh,
)
logger = logging.getLogger(__name__)

SALESFORCE_SCOPES = "api refresh_token"
SALESFORCE_AUTHORIZE_URL = "https://login.salesforce.com/services/oauth2/authorize"
SALESFORCE_TOKEN_URL = "https://login.salesforce.com/services/oauth2/token"
SALESFORCE_AUTHORIZE_URL_SANDBOX = "https://test.salesforce.com/services/oauth2/authorize"
SALESFORCE_TOKEN_URL_SANDBOX = "https://test.salesforce.com/services/oauth2/token"
TOKEN_REFRESH_BUFFER_SEC = 300

_STAGING_ENVIRONMENTS = frozenset({"staging", "sandbox", "development", "dev", "test"})


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"salesforce", "sfdc", "salesforcecrm"}:
        return "salesforce"
    return key


def is_staging_environment(environment_name: str | None) -> bool:
    return (environment_name or "production").strip().lower() in _STAGING_ENVIRONMENTS


def salesforce_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    if is_staging_environment(environment_name):
        client_id = (settings.salesforce_sandbox_client_id or settings.salesforce_client_id or "").strip()
        client_secret = (
            settings.salesforce_sandbox_client_secret or settings.salesforce_client_secret or ""
        ).strip()
    else:
        client_id = (settings.salesforce_client_id or "").strip()
        client_secret = (settings.salesforce_client_secret or "").strip()
    return client_id, client_secret


def salesforce_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = salesforce_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def _authorize_base(settings: Settings, environment_name: str | None) -> tuple[str, str]:
    if is_staging_environment(environment_name):
        return SALESFORCE_AUTHORIZE_URL_SANDBOX, SALESFORCE_TOKEN_URL_SANDBOX
    return SALESFORCE_AUTHORIZE_URL, SALESFORCE_TOKEN_URL


def salesforce_redirect_uri(settings: Settings) -> str:
    api_base = (settings.api_public_url or "").strip().rstrip("/")
    if api_base:
        return f"{api_base}/api/connectors/oauth/salesforce/callback"
    base = (settings.public_app_url or "").strip().rstrip("/")
    if base:
        return f"{base}/api/connectors/oauth/salesforce/callback"
    return "http://localhost:8000/api/connectors/oauth/salesforce/callback"


def salesforce_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    *,
    environment_name: str | None = None,
    code_challenge: str | None = None,
) -> str:
    authorize_url = (
        SALESFORCE_AUTHORIZE_URL_SANDBOX
        if is_staging_environment(environment_name)
        else SALESFORCE_AUTHORIZE_URL
    )
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SALESFORCE_SCOPES,
        "state": state,
    }
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    query = urlencode(params)
    return f"{authorize_url}?{query}"


def _token_payload_from_response(data: dict[str, Any]) -> dict[str, Any]:
    issued_at = data.get("issued_at")
    expires_in = 7200
    now = int(time.time())
    expires_at = now + expires_in
    if issued_at:
        try:
            expires_at = int(int(issued_at) / 1000) + expires_in
        except (TypeError, ValueError):
            pass
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "instance_url": data.get("instance_url"),
        "id": data.get("id"),
        "token_type": data.get("token_type") or "Bearer",
        "signature": data.get("signature"),
        "scope": data.get("scope"),
        "expires_at": expires_at,
        "updated_at": now,
    }


def exchange_salesforce_code(
    code: str,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    environment_name: str | None = None,
    code_verifier: str | None = None,
) -> dict[str, Any]:
    _, token_url = _authorize_base(Settings(), environment_name)
    data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }
    if code_verifier:
        data["code_verifier"] = code_verifier
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return _token_payload_from_response(response.json())


def refresh_salesforce_token(
    refresh_token: str,
    *,
    client_id: str,
    client_secret: str,
    environment_name: str | None = None,
) -> dict[str, Any]:
    _, token_url = _authorize_base(Settings(), environment_name)
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        payload = _token_payload_from_response(response.json())
        if not payload.get("refresh_token"):
            payload["refresh_token"] = refresh_token
        return payload


def refresh_salesforce_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = salesforce_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "Salesforce OAuth is not configured on the server"
    if not settings.connector_secrets_encryption_key:
        return None, "Connector secrets encryption is not configured"

    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return None, "OAuth not completed"

    refresh_token = tokens.get("refresh_token")
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and refresh_token:
        try:
            tokens = refresh_salesforce_token(
                str(refresh_token),
                client_id=client_id,
                client_secret=client_secret,
                environment_name=env,
            )
            store_oauth_tokens(client, org_id, connector_id, tokens, settings)
            logger.info("salesforce_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            return None, f"Token refresh failed: {exc}"

    return tokens, None


def complete_salesforce_oauth_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    code: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
    reconnect: bool = False,
    code_verifier: str | None = None,
) -> None:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = salesforce_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("Salesforce OAuth is not configured")
    if not code_verifier:
        raise ValueError("Salesforce PKCE code_verifier missing from OAuth state")

    tokens = exchange_salesforce_code(
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=salesforce_redirect_uri(settings),
        environment_name=env,
        code_verifier=code_verifier,
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
    config["oauth_provider"] = "salesforce"
    config["instance_url"] = tokens.get("instance_url")
    if not (config.get("webhook_secret") or "").strip():
        config["webhook_secret"] = secrets.token_hex(32)
    sf_id = tokens.get("id")
    if isinstance(sf_id, str) and "/id/" in sf_id:
        parts = sf_id.split("/id/")
        if len(parts) > 1:
            org_part = parts[1].split("/")[0]
            if org_part:
                config["salesforce_org_id"] = org_part
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()

    from app.services.salesforce_trigger_service import on_salesforce_connector_connected

    on_salesforce_connector_connected(client, org_id, connector_id, settings)


def ensure_salesforce_access_token(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None]:
    token, _, err = ensure_salesforce_session(
        client, org_id, connector_id, settings, environment_name=environment_name
    )
    return token, err


def _connector_instance_url(client: Any, org_id: str, connector_id: str) -> str | None:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = dict((row.data or [{}])[0].get("config") or {})
    url = (config.get("instance_url") or "").strip()
    return url or None


def ensure_salesforce_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Return (access_token, instance_url, error)."""
    tokens, err = refresh_salesforce_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=environment_name
    )
    if err or not tokens:
        return None, None, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    instance_url = (tokens.get("instance_url") or _connector_instance_url(client, org_id, connector_id) or "").strip()
    if not token:
        return None, None, "OAuth not completed"
    if not instance_url:
        return None, None, "Salesforce instance_url missing; reconnect OAuth"
    return token, instance_url.rstrip("/"), None


def salesforce_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not salesforce_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and not tokens.get("refresh_token"):
        return "auth_expired"
    _, err = ensure_salesforce_access_token(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err:
        return "auth_expired"
    return "connected"
