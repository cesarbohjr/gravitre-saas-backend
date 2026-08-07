"""Workday OAuth 2.0 client credentials + token lifecycle (STA-59)."""
from __future__ import annotations

import logging
import re
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

WORKDAY_SCOPE = "openid profile"
TOKEN_REFRESH_BUFFER_SEC = 300

_STAGING_ENVIRONMENTS = frozenset({"staging", "sandbox", "development", "dev", "test"})


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"workday", "workdayhris", "workdayhr"}:
        return "workday"
    return key


def is_staging_environment(environment_name: str | None) -> bool:
    return (environment_name or "production").strip().lower() in _STAGING_ENVIRONMENTS


def workday_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    if is_staging_environment(environment_name):
        client_id = (settings.workday_sandbox_client_id or settings.workday_client_id or "").strip()
        client_secret = (
            settings.workday_sandbox_client_secret or settings.workday_client_secret or ""
        ).strip()
    else:
        client_id = (settings.workday_client_id or "").strip()
        client_secret = (settings.workday_client_secret or "").strip()
    return client_id, client_secret


def workday_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = workday_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def workday_redirect_uri(settings: Settings) -> str:
    return connector_oauth_callback_url(
        public_app_url=settings.public_app_url,
        api_public_url=settings.api_public_url,
        vendor="workday",
    )


def normalize_tenant_url(tenant_url: str) -> str:
    """Return Workday hostname without scheme or trailing slash."""
    value = tenant_url.strip().rstrip("/")
    if value.startswith("https://"):
        value = value[len("https://") :]
    elif value.startswith("http://"):
        value = value[len("http://") :]
    return value.split("/", 1)[0]


def normalize_tenant_name(tenant: str | None) -> str:
    value = (tenant or "").strip()
    if not value:
        raise ValueError("Workday tenant name is required")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Workday tenant name contains invalid characters")
    return value


def workday_token_url(*, tenant_url: str, tenant: str) -> str:
    host = normalize_tenant_url(tenant_url)
    return f"https://{host}/ccx/oauth2/{tenant}/token"


def workday_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    *,
    tenant_url: str,
    tenant: str,
    environment_name: str | None = None,
) -> str:
    """Authorization URL for delegated OAuth; ISU flows complete via client credentials."""
    _ = environment_name
    host = normalize_tenant_url(tenant_url)
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": WORKDAY_SCOPE,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"https://{host}/ccx/oauth2/{tenant}/authorize?{query}"


def workday_api_base_url(*, tenant_url: str, tenant: str, environment_name: str | None = None) -> str:
    _ = environment_name
    host = normalize_tenant_url(tenant_url)
    return f"https://{host}/ccx/api/v1/{tenant}"


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
    tenant_url: str,
    tenant: str,
    client_id: str,
    client_secret: str,
    body: dict[str, str],
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            workday_token_url(tenant_url=tenant_url, tenant=tenant),
            data=body,
            auth=(client_id, client_secret),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return _token_payload_from_response(response.json())


def exchange_workday_client_credentials(
    *,
    tenant_url: str,
    tenant: str,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    return _token_request(
        tenant_url=tenant_url,
        tenant=tenant,
        client_id=client_id,
        client_secret=client_secret,
        body={"grant_type": "client_credentials"},
    )


def exchange_workday_code(
    code: str,
    *,
    tenant_url: str,
    tenant: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    return _token_request(
        tenant_url=tenant_url,
        tenant=tenant,
        client_id=client_id,
        client_secret=client_secret,
        body={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )


def refresh_workday_token(
    refresh_token: str,
    *,
    tenant_url: str,
    tenant: str,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    payload = _token_request(
        tenant_url=tenant_url,
        tenant=tenant,
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


def _connector_tenant_config(client: Any, org_id: str, connector_id: str) -> tuple[str | None, str | None]:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((row.data or [{}])[0], key="config")
    tenant_url = (config.get("tenant_url") or config.get("tenantUrl") or "").strip()
    tenant = (config.get("tenant") or config.get("tenant_name") or config.get("tenantName") or "").strip()
    return tenant_url or None, tenant or None


def persist_workday_tenant_config(
    client: Any,
    org_id: str,
    connector_id: str,
    *,
    tenant_url: str,
    tenant: str,
) -> None:
    existing = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((existing.data or [{}])[0], key="config")
    config["tenant_url"] = normalize_tenant_url(tenant_url)
    config["tenant"] = normalize_tenant_name(tenant)
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def refresh_workday_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = workday_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "Workday OAuth is not configured on the server"
    if not settings.connector_secrets_encryption_key:
        return None, "Connector secrets encryption is not configured"

    tenant_url, tenant = _connector_tenant_config(client, org_id, connector_id)
    if not tenant_url or not tenant:
        return None, "Workday tenant_url missing; reconnect OAuth"

    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return None, "OAuth not completed"

    refresh_token = tokens.get("refresh_token")
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC):
        try:
            if refresh_token:
                tokens = refresh_workday_token(
                    str(refresh_token),
                    tenant_url=tenant_url,
                    tenant=tenant,
                    client_id=client_id,
                    client_secret=client_secret,
                )
            else:
                tokens = exchange_workday_client_credentials(
                    tenant_url=tenant_url,
                    tenant=tenant,
                    client_id=client_id,
                    client_secret=client_secret,
                )
            store_oauth_tokens(client, org_id, connector_id, tokens, settings)
            logger.info("workday_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            return None, f"Token refresh failed: {exc}"

    return tokens, None


def ensure_workday_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Return (access_token, tenant_url, tenant, api_base_url, error)."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    tokens, err = refresh_workday_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not tokens:
        return None, None, None, None, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    tenant_url, tenant = _connector_tenant_config(client, org_id, connector_id)
    if not token:
        return None, None, None, None, "OAuth not completed"
    if not tenant_url or not tenant:
        return None, None, None, None, "Workday tenant_url missing; reconnect OAuth"
    return (
        token,
        tenant_url,
        tenant,
        workday_api_base_url(tenant_url=tenant_url, tenant=tenant, environment_name=env),
        None,
    )


def complete_workday_oauth_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    code: str | None,
    settings: Settings,
    *,
    tenant_url: str | None = None,
    tenant: str | None = None,
    environment_name: str | None = None,
    reconnect: bool = False,
    use_client_credentials: bool = True,
) -> None:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = workday_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("Workday OAuth is not configured")

    existing = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((existing.data or [{}])[0], key="config")
    resolved_tenant_url = normalize_tenant_url(
        tenant_url or config.get("tenant_url") or config.get("tenantUrl") or ""
    )
    resolved_tenant = normalize_tenant_name(
        tenant or config.get("tenant") or config.get("tenant_name") or config.get("tenantName")
    )
    if not resolved_tenant_url:
        raise ValueError("Workday tenant_url is required in connector config")

    if use_client_credentials or not code:
        tokens = exchange_workday_client_credentials(
            tenant_url=resolved_tenant_url,
            tenant=resolved_tenant,
            client_id=client_id,
            client_secret=client_secret,
        )
    else:
        tokens = exchange_workday_code(
            code,
            tenant_url=resolved_tenant_url,
            tenant=resolved_tenant,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=workday_redirect_uri(settings),
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
    config["oauth_provider"] = "workday"
    config["tenant_url"] = resolved_tenant_url
    config["tenant"] = resolved_tenant
    config["sandbox"] = is_staging_environment(env)
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def workday_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not workday_oauth_configured(settings, env):
        return "misconfigured"
    tenant_url, tenant = _connector_tenant_config(client, org_id, connector_id)
    if not tenant_url or not tenant:
        return "pending_auth"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    _, _, _, _, err = ensure_workday_session(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err:
        return "auth_expired"
    return "connected"
