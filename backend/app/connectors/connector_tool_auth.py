"""Resolve connector credentials for agent tools (OAuth with API-key fallback)."""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.repository import get_decrypted_secret
from app.connectors.hubspot_oauth import load_oauth_tokens


def resolve_github_access_token(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str | None:
    """OAuth access token first, then stored PAT."""
    token, _err = ensure_generic_session(
        client,
        org_id,
        connector_id,
        settings,
        vendor="github",
        environment_name=environment_name,
    )
    if token:
        return token
    tokens = load_oauth_tokens(client, connector_id, settings)
    if tokens and tokens.get("access_token"):
        return str(tokens["access_token"])
    pat = get_decrypted_secret(client, connector_id, "token", settings)
    return (pat or "").strip() or None


def resolve_zendesk_auth(
    client: Any,
    org_id: str,
    connector: dict[str, Any],
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str | None, str | None, str | None]:
    """
    Returns (subdomain, email, api_token, oauth_access_token).
    OAuth token is preferred by callers when present.
    """
    cid = str(connector["id"])
    cfg = connector.get("config") or {}
    subdomain = str(cfg.get("subdomain") or cfg.get("zendesk_subdomain") or "").strip()
    if not subdomain:
        raise ValueError("Zendesk connector missing subdomain in config")

    oauth_token, _err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="zendesk",
        environment_name=environment_name,
    )
    if oauth_token:
        return subdomain, None, None, oauth_token

    tokens = load_oauth_tokens(client, cid, settings)
    if tokens and tokens.get("access_token"):
        return subdomain, None, None, str(tokens["access_token"])

    email = get_decrypted_secret(client, cid, "email", settings)
    api_token = get_decrypted_secret(client, cid, "api_token", settings)
    return subdomain, (email or "").strip() or None, (api_token or "").strip() or None, None


def resolve_connectwise_auth(
    client: Any,
    org_id: str,
    connector: dict[str, Any],
    settings: Settings,
) -> dict[str, str]:
    """Return ConnectWise Manage API credentials from connector config + secrets."""
    _ = org_id
    cid = str(connector["id"])
    cfg = connector.get("config") or {}
    site_url = str(cfg.get("site_url") or cfg.get("siteUrl") or "").strip()
    company_id = str(cfg.get("company_id") or cfg.get("companyId") or "").strip()
    client_id = str(cfg.get("client_id") or cfg.get("clientId") or "").strip()
    default_board_id = str(cfg.get("default_board_id") or cfg.get("defaultBoardId") or "").strip()
    if not site_url or not company_id:
        raise ValueError("ConnectWise connector missing site_url or company_id in config")
    if not client_id:
        raise ValueError("ConnectWise connector missing client_id in config")
    public_key = get_decrypted_secret(client, cid, "public_key", settings)
    private_key = get_decrypted_secret(client, cid, "private_key", settings)
    if not public_key or not private_key:
        raise ValueError("ConnectWise public_key/private_key secrets not configured")
    out = {
        "site_url": site_url,
        "company_id": company_id,
        "client_id": client_id,
        "public_key": str(public_key).strip(),
        "private_key": str(private_key).strip(),
    }
    if default_board_id:
        out["default_board_id"] = default_board_id
    return out


def resolve_slack_bot_token(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
) -> str | None:
    token = get_decrypted_secret(client, connector_id, "token", settings)
    if token:
        return token.strip()
    tokens = load_oauth_tokens(client, connector_id, settings)
    if tokens and tokens.get("access_token"):
        return str(tokens["access_token"]).strip()
    return None


def resolve_microsoft365_access_token(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str | None:
    token, _err = ensure_generic_session(
        client,
        org_id,
        connector_id,
        settings,
        vendor="microsoft365",
        environment_name=environment_name,
    )
    if token:
        return token
    tokens = load_oauth_tokens(client, connector_id, settings)
    if tokens and tokens.get("access_token"):
        return str(tokens["access_token"]).strip()
    return None
