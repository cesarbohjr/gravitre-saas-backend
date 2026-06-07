"""Generic OAuth 2.0 authorization-code flow for registry-based connectors."""
from __future__ import annotations

import logging
import os
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.connectors.hubspot_oauth import (
    _connector_environment,
    load_oauth_tokens,
    mark_connector_oauth_failure,
    mark_connector_oauth_success,
    store_oauth_tokens,
    token_needs_refresh,
)
from app.connectors.oauth_provider_registry import (
    OAuthProviderSpec,
    OAUTH_PROVIDER_REGISTRY,
    provider_context_from_connector_config,
    resolve_url_template,
)
from app.connectors.oauth_provider_registry import TokenRequestStyle

logger = logging.getLogger(__name__)

TOKEN_REFRESH_BUFFER_SEC = 300


def generic_credentials(settings: Settings, vendor: str) -> tuple[str, str]:
    key = vendor.strip().lower().replace("-", "_")
    env_prefix = key.upper()
    client_id = (os.environ.get(f"{env_prefix}_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get(f"{env_prefix}_CLIENT_SECRET") or "").strip()
    if not client_id:
        client_id = (getattr(settings, f"{key}_client_id", None) or "").strip()
    if not client_secret:
        client_secret = (getattr(settings, f"{key}_client_secret", None) or "").strip()
    return client_id, client_secret


def generic_oauth_configured(settings: Settings, vendor: str, environment_name: str | None = None) -> bool:
    _ = environment_name
    client_id, client_secret = generic_credentials(settings, vendor)
    return bool(client_id and client_secret)


def generic_redirect_uri(settings: Settings, vendor: str) -> str:
    api_base = (settings.api_public_url or "").strip().rstrip("/")
    if api_base:
        return f"{api_base}/api/connectors/oauth/{vendor}/callback"
    base = (settings.public_app_url or "").strip().rstrip("/")
    if base:
        return f"{base}/api/connectors/oauth/{vendor}/callback"
    return f"http://localhost:8000/api/connectors/oauth/{vendor}/callback"


def _token_payload_from_response(
    data: dict[str, Any],
    *,
    vendor: str,
    org_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    expires_in = int(data.get("expires_in") or 0)
    now = int(time.time())
    scope = data.get("scope")
    if isinstance(scope, list):
        scope = " ".join(scope)
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_at": now + expires_in if expires_in else None,
        "token_type": data.get("token_type") or "bearer",
        "scope": scope,
        "vendor": vendor,
        "org_id": org_id,
        "user_id": user_id,
        "updated_at": now,
    }


def _parse_token_response(
    response: httpx.Response,
    *,
    as_json: bool,
    vendor: str,
    org_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    if as_json:
        return _token_payload_from_response(response.json(), vendor=vendor, org_id=org_id, user_id=user_id)
    from urllib.parse import parse_qs

    parsed = {k: v[0] for k, v in parse_qs(response.text).items()}
    return _token_payload_from_response(parsed, vendor=vendor, org_id=org_id, user_id=user_id)


def _exchange_token(
    spec: OAuthProviderSpec,
    *,
    body: dict[str, str],
    client_id: str,
    client_secret: str,
    org_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    headers = {"Accept": spec.accept_header}
    with httpx.Client(timeout=30.0) as client:
        if spec.token_style == TokenRequestStyle.JSON:
            response = client.post(
                spec.token_url,
                json=body,
                auth=(client_id, client_secret),
                headers={**headers, "Content-Type": "application/json"},
            )
        elif spec.token_style == TokenRequestStyle.BASIC_AUTH:
            response = client.post(
                spec.token_url,
                data=body,
                auth=(client_id, client_secret),
                headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
            )
        else:
            payload = {**body, "client_id": client_id, "client_secret": client_secret}
            response = client.post(
                spec.token_url,
                data=payload,
                headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
            )
        response.raise_for_status()
        return _parse_token_response(
            response,
            as_json=spec.token_response_json,
            vendor=spec.vendor,
            org_id=org_id,
            user_id=user_id,
        )


def exchange_generic_code(
    spec: OAuthProviderSpec,
    code: str,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code_verifier: str | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if spec.requires_pkce:
        if not code_verifier:
            raise ValueError(f"{spec.vendor} requires PKCE code_verifier")
        body["code_verifier"] = code_verifier
    return _exchange_token(
        spec,
        body=body,
        client_id=client_id,
        client_secret=client_secret,
        org_id=org_id,
        user_id=user_id,
    )


def refresh_generic_token(
    spec: OAuthProviderSpec,
    refresh_token: str,
    *,
    client_id: str,
    client_secret: str,
    org_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    return _exchange_token(
        spec,
        body={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        client_id=client_id,
        client_secret=client_secret,
        org_id=org_id,
        user_id=user_id,
    )


def generic_authorize_url(
    spec: OAuthProviderSpec,
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    subdomain: str = "",
    instance_url: str = "",
    code_challenge: str | None = None,
) -> str:
    authorize_url = resolve_url_template(
        spec.authorize_url,
        subdomain=subdomain,
        instance_url=instance_url,
    )
    params: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    }
    if spec.scopes:
        params["scope"] = spec.scopes
    if spec.requires_pkce:
        if not code_challenge:
            raise ValueError(f"{spec.vendor} requires PKCE code_challenge")
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    for key, value in spec.authorize_extra.items():
        params[key] = resolve_url_template(value, subdomain=subdomain, instance_url=instance_url)
    return f"{authorize_url}?{urlencode(params)}"


def persist_generic_oauth_connector_config(
    client: Any,
    org_id: str,
    connector_id: str,
    *,
    vendor: str,
    subdomain: str | None = None,
    instance_url: str | None = None,
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
    config["oauth_provider"] = vendor
    config["auth_type"] = "oauth"
    if subdomain:
        config["subdomain"] = subdomain.strip()
        if vendor == "zendesk":
            config["zendesk_subdomain"] = subdomain.strip()
    if instance_url:
        config["instance_url"] = instance_url.strip().rstrip("/")
        if vendor == "odoo":
            config["odoo_url"] = instance_url.strip().rstrip("/")
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def _connector_context(client: Any, org_id: str, connector_id: str) -> dict[str, str]:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = dict((row.data or [{}])[0].get("config") or {})
    return provider_context_from_connector_config(config)


def _resolved_spec(vendor: str, *, subdomain: str, instance_url: str) -> OAuthProviderSpec:
    base = OAUTH_PROVIDER_REGISTRY[vendor]
    return OAuthProviderSpec(
        vendor=base.vendor,
        authorize_url=resolve_url_template(base.authorize_url, subdomain=subdomain, instance_url=instance_url),
        token_url=resolve_url_template(base.token_url, subdomain=subdomain, instance_url=instance_url),
        scopes=base.scopes,
        token_style=base.token_style,
        authorize_extra=base.authorize_extra,
        requires_subdomain=base.requires_subdomain,
        requires_instance_url=base.requires_instance_url,
        requires_pkce=base.requires_pkce,
        partner_gated=base.partner_gated,
        accept_header=base.accept_header,
        token_response_json=base.token_response_json,
        notes=base.notes,
    )


def validate_generic_oauth_prerequisites(
    spec: OAuthProviderSpec,
    *,
    subdomain: str | None,
    instance_url: str | None,
) -> None:
    if spec.requires_subdomain and not (subdomain or "").strip():
        raise ValueError(f"{spec.vendor} requires subdomain before OAuth")
    if spec.requires_instance_url and not (instance_url or "").strip():
        raise ValueError(f"{spec.vendor} requires instanceUrl before OAuth")


def complete_generic_oauth_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    code: str,
    settings: Settings,
    *,
    vendor: str,
    environment_name: str | None = None,
    reconnect: bool = False,
    code_verifier: str | None = None,
    user_id: str | None = None,
) -> None:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = generic_credentials(settings, vendor)
    if not client_id or not client_secret:
        raise ValueError(f"{vendor} OAuth is not configured")

    ctx = _connector_context(client, org_id, connector_id)
    spec = _resolved_spec(vendor, subdomain=ctx["subdomain"], instance_url=ctx["instance_url"])
    if spec.requires_pkce and not code_verifier:
        raise ValueError(f"{vendor} PKCE code_verifier missing from OAuth state")

    redirect_uri = generic_redirect_uri(settings, vendor)
    tokens = exchange_generic_code(
        spec,
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
        org_id=org_id,
        user_id=user_id,
    )
    if not tokens.get("access_token"):
        raise ValueError(f"{vendor} token exchange did not return access_token")

    store_oauth_tokens(client, org_id, connector_id, tokens, settings)
    mark_connector_oauth_success(
        client,
        org_id,
        connector_id,
        tokens,
        environment_name=env,
        reconnect=reconnect,
    )
    persist_generic_oauth_connector_config(
        client,
        org_id,
        connector_id,
        vendor=vendor,
        subdomain=ctx["subdomain"] or None,
        instance_url=ctx["instance_url"] or None,
    )


def ensure_generic_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    vendor: str,
    environment_name: str | None = None,
) -> tuple[str | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return None, f"{vendor} OAuth not connected"

    ctx = _connector_context(client, org_id, connector_id)
    spec = _resolved_spec(vendor, subdomain=ctx["subdomain"], instance_url=ctx["instance_url"])

    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and tokens.get("refresh_token"):
        client_id, client_secret = generic_credentials(settings, vendor)
        if not client_id or not client_secret:
            return None, f"{vendor} OAuth is not configured"
        try:
            refreshed = refresh_generic_token(
                spec,
                str(tokens["refresh_token"]),
                client_id=client_id,
                client_secret=client_secret,
                org_id=org_id,
                user_id=str(tokens.get("user_id") or "") or None,
            )
            merged = {**tokens, **refreshed}
            store_oauth_tokens(client, org_id, connector_id, merged, settings)
            tokens = merged
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            logger.warning("generic oauth refresh failed vendor=%s err=%s", vendor, type(exc).__name__)
            return None, "Token refresh failed"

    access = str(tokens.get("access_token") or "").strip()
    if not access:
        return None, f"{vendor} access token missing"
    return access, None


def generic_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    vendor: str,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not generic_oauth_configured(settings, vendor, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return "pending_auth"
    token, err = ensure_generic_session(
        client,
        org_id,
        connector_id,
        settings,
        vendor=vendor,
        environment_name=env,
    )
    if err or not token:
        return "auth_expired"
    return "connected"
