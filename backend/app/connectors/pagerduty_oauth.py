"""PagerDuty OAuth2 + token lifecycle (STA-37)."""
from __future__ import annotations

import logging
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.connectors.pagerduty import api_request, fetch_current_user
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

PAGERDUTY_SCOPES = "openid users.read incidents.read incidents.write"
PAGERDUTY_AUTHORIZE_URL = "https://app.pagerduty.com/oauth/authorize"
PAGERDUTY_TOKEN_URL = "https://app.pagerduty.com/oauth/token"
TOKEN_REFRESH_BUFFER_SEC = 300

V1_WEBHOOK_EVENTS = ("incident.triggered", "incident.acknowledged")


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"pagerduty", "pd"}:
        return "pagerduty"
    return key


def pagerduty_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    _ = environment_name
    client_id = (settings.pagerduty_client_id or "").strip()
    client_secret = (settings.pagerduty_client_secret or "").strip()
    return client_id, client_secret


def pagerduty_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = pagerduty_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def pagerduty_redirect_uri(settings: Settings) -> str:
    """Must match the redirect URL registered in the PagerDuty OAuth app (often locked after create)."""
    app_base = (settings.public_app_url or "").strip().rstrip("/")
    if app_base:
        return f"{app_base}/api/auth/callback/pagerduty"
    api_base = (settings.api_public_url or "").strip().rstrip("/")
    if api_base:
        return f"{api_base}/api/connectors/oauth/pagerduty/callback"
    return "http://localhost:3000/api/auth/callback/pagerduty"


def pagerduty_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": PAGERDUTY_SCOPES,
            "state": state,
        }
    )
    return f"{PAGERDUTY_AUTHORIZE_URL}?{query}"


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


def exchange_pagerduty_code(
    code: str,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            PAGERDUTY_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return _token_payload_from_response(response.json())


def refresh_pagerduty_token(
    refresh_token: str,
    *,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            PAGERDUTY_TOKEN_URL,
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


def refresh_pagerduty_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = pagerduty_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "PagerDuty OAuth is not configured on the server"
    if not settings.connector_secrets_encryption_key:
        return None, "Connector secrets encryption is not configured"

    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return None, "OAuth not completed"

    refresh_token = tokens.get("refresh_token")
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and refresh_token:
        try:
            tokens = refresh_pagerduty_token(
                str(refresh_token),
                client_id=client_id,
                client_secret=client_secret,
            )
            store_oauth_tokens(client, org_id, connector_id, tokens, settings)
            logger.info("pagerduty_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            return None, f"Token refresh failed: {exc}"

    return tokens, None


def ensure_pagerduty_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None]:
    """Return (access_token, error)."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    tokens, err = refresh_pagerduty_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not tokens:
        return None, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    if not token:
        return None, "OAuth not completed"
    return token, None


def try_register_webhook_subscription(
    access_token: str,
    *,
    inbound_url: str,
    signing_secret: str,
    events: tuple[str, ...] = V1_WEBHOOK_EVENTS,
) -> dict[str, Any] | None:
    """Create PagerDuty webhook subscription; returns subscription dict or None on failure."""
    user = fetch_current_user(access_token)
    account = user.get("account") or {}
    account_id = account.get("id") if isinstance(account, dict) else None
    if not account_id:
        return None
    body = {
        "webhook_subscription": {
            "type": "webhook_subscription",
            "name": "Gravitre Operator",
            "delivery_method": {
                "type": "http_delivery_method",
                "url": inbound_url,
                "custom_headers": {},
            },
            "filter": {"type": "account_reference", "id": account_id},
            "events": list(events),
        }
    }
    try:
        result = api_request("POST", "/webhook_subscriptions", access_token, json_body=body)
    except httpx.HTTPError as exc:
        logger.warning("pagerduty_webhook_subscription_failed error=%s", exc)
        return None
    subscription = safe_normalize_stored_dict(result, key='webhook_subscription') or safe_normalize_stored_dict(result)
    delivery = subscription.get("delivery_method") or {}
    if isinstance(delivery, dict) and delivery.get("secret"):
        subscription["_signing_secret"] = delivery.get("secret")
    subscription["_signing_secret"] = subscription.get("_signing_secret") or signing_secret
    return subscription


def complete_pagerduty_oauth_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    code: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
    reconnect: bool = False,
    inbound_webhook_url: str | None = None,
) -> None:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = pagerduty_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("PagerDuty OAuth is not configured")

    tokens = exchange_pagerduty_code(
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=pagerduty_redirect_uri(settings),
    )
    access_token = str(tokens.get("access_token") or "")
    if not access_token:
        raise ValueError("PagerDuty token exchange did not return access_token")

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
    config["oauth_provider"] = "pagerduty"
    webhook_secret = (config.get("webhook_secret") or "").strip() or secrets.token_hex(32)
    config["webhook_secret"] = webhook_secret

    user = fetch_current_user(access_token)
    if user.get("id"):
        config["pagerduty_user_id"] = str(user["id"])
    if user.get("email"):
        config["pagerduty_requester_email"] = str(user["email"])
    account = user.get("account") or {}
    if isinstance(account, dict) and account.get("id"):
        config["pagerduty_account_id"] = str(account["id"])

    if inbound_webhook_url:
        subscription = try_register_webhook_subscription(
            access_token,
            inbound_url=inbound_webhook_url,
            signing_secret=webhook_secret,
        )
        if subscription:
            if subscription.get("id"):
                config["pagerduty_webhook_subscription_id"] = str(subscription["id"])
            signing = subscription.get("_signing_secret")
            if signing:
                config["pagerduty_signing_secret"] = str(signing)

    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def pagerduty_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not pagerduty_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and not tokens.get("refresh_token"):
        return "auth_expired"
    _, err = ensure_pagerduty_session(client, org_id, connector_id, settings, environment_name=env)
    if err:
        return "auth_expired"
    return "connected"
