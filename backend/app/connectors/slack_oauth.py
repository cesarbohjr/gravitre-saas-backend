"""Slack OAuth v2 + bot token storage for connector tools."""
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
)
from app.connectors.repository import get_decrypted_secret, set_secret

logger = logging.getLogger(__name__)

SLACK_SCOPES = (
    "chat:write,channels:read,channels:history,channels:join,users:read,"
    "channels:manage,files:write,reactions:write,workflow.steps:execute"
)
SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_AUTH_TEST_URL = "https://slack.com/api/auth.test"


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower()
    if key == "slack":
        return "slack"
    return key


def slack_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    _ = environment_name
    client_id = (settings.slack_client_id or "").strip()
    client_secret = (settings.slack_client_secret or "").strip()
    return client_id, client_secret


def slack_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = slack_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def slack_redirect_uri(settings: Settings) -> str:
    return connector_oauth_callback_url(
        public_app_url=settings.public_app_url,
        api_public_url=settings.api_public_url,
        vendor="slack",
    )


def slack_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "scope": SLACK_SCOPES,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{SLACK_AUTHORIZE_URL}?{query}"


def exchange_slack_code(
    code: str,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            SLACK_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise ValueError(data.get("error", "Slack token exchange failed"))
        return data


def _token_payload_from_slack(data: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    return {
        "access_token": data.get("access_token"),
        "token_type": data.get("token_type") or "bot",
        "scope": data.get("scope"),
        "bot_user_id": data.get("bot_user_id"),
        "app_id": data.get("app_id"),
        "team": data.get("team"),
        "authed_user": data.get("authed_user"),
        "updated_at": now,
    }


def complete_slack_oauth_connection(
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
    client_id, client_secret = slack_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("Slack OAuth is not configured")

    try:
        data = exchange_slack_code(
            code,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=slack_redirect_uri(settings),
        )
    except (httpx.HTTPError, ValueError) as exc:
        mark_connector_oauth_failure(client, org_id, connector_id, str(exc), environment_name=env)
        raise

    bot_token = str(data.get("access_token") or "")
    if not bot_token:
        mark_connector_oauth_failure(
            client, org_id, connector_id, "missing_bot_token", environment_name=env
        )
        raise ValueError("Slack token exchange did not return access_token")

    tokens = _token_payload_from_slack(data)
    store_oauth_tokens(client, org_id, connector_id, tokens, settings)
    set_secret(client, org_id, connector_id, "token", bot_token, settings)
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
    config["auth_type"] = "oauth"
    config["oauth_provider"] = "slack"
    if data.get("app_id"):
        config["slack_app_id"] = str(data["app_id"])
    elif (settings.slack_app_id or "").strip():
        config["slack_app_id"] = settings.slack_app_id.strip()
    if data.get("bot_user_id"):
        config["slack_bot_user_id"] = str(data["bot_user_id"])
    team = data.get("team") or {}
    if isinstance(team, dict):
        if team.get("id"):
            config["slack_team_id"] = str(team["id"])
        if team.get("name"):
            config["slack_team_name"] = str(team["name"])

    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()


def slack_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not slack_oauth_configured(settings, env):
        return "misconfigured"
    token = get_decrypted_secret(client, connector_id, "token", settings)
    if not token:
        oauth_tokens = load_oauth_tokens(client, connector_id, settings)
        if oauth_tokens and oauth_tokens.get("access_token"):
            token = str(oauth_tokens["access_token"])
    if not token:
        return "pending_auth"
    try:
        with httpx.Client(timeout=15.0) as http:
            response = http.post(
                SLACK_AUTH_TEST_URL,
                headers={"Authorization": f"Bearer {token}"},
            )
            data = response.json()
            if data.get("ok"):
                return "connected"
    except httpx.HTTPError:
        pass
    return "auth_expired"
