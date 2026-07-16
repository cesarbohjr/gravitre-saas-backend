"""Plaid Link integration (NOT generic OAuth callback).

Platform env: PLAID_CLIENT_ID + PLAID_SECRET (sandbox by default).
Per-org flow:
  1. Backend creates a link_token (POST /link/token/create)
  2. Frontend opens Plaid Link with that token
  3. Frontend receives public_token on success
  4. Backend exchanges public_token via /item/public_token/exchange
  5. access_token stored on the org's plaid connector

Do not register Plaid in oauth_provider_registry or /api/connectors/oauth/plaid/*.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import (
    get_connector,
    get_connector_by_type,
    set_secret,
    update_connector,
)
from app.services.plaid_tools import resolve_plaid_api_base

PLAID_LINK_ARCHITECTURE = "public_token_exchange"
TIMEOUT_SEC = 45.0
DEFAULT_PRODUCTS = ["transactions", "auth"]
DEFAULT_COUNTRY_CODES = ["US"]
# Must match Plaid Dashboard → Allowed redirect URIs (OAuth institutions).
DEFAULT_REDIRECT_URI = "https://gravitre.app/connectors"


class PlaidLinkError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def plaid_platform_credentials(settings: Settings) -> tuple[str, str]:
    """Return (client_id, secret) from platform env / settings."""
    import os

    client_id = (
        (os.environ.get("PLAID_CLIENT_ID") or "").strip()
        or (settings.plaid_client_id or "").strip()
    )
    secret = (
        (os.environ.get("PLAID_SECRET") or "").strip()
        or (os.environ.get("PLAID_CLIENT_SECRET") or "").strip()
        or (settings.plaid_secret or "").strip()
    )
    return client_id, secret


def plaid_link_configured(settings: Settings) -> bool:
    client_id, secret = plaid_platform_credentials(settings)
    return bool(client_id and secret)


def _plaid_post(api_base: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}{path}"
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.post(url, json=body, headers={"Content-Type": "application/json"})
    if response.status_code >= 400:
        raise PlaidLinkError(
            (response.text or f"Plaid API error {response.status_code}")[:500],
            status_code=response.status_code,
        )
    try:
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        raise PlaidLinkError("Invalid JSON from Plaid", status_code=502) from exc
    return data if isinstance(data, dict) else {"value": data}


def create_link_token(
    settings: Settings,
    *,
    client_user_id: str,
    redirect_uri: str | None = None,
) -> dict[str, Any]:
    """Create a Plaid Link token for the sandbox (or configured) environment."""
    client_id, secret = plaid_platform_credentials(settings)
    if not client_id or not secret:
        raise PlaidLinkError(
            "Plaid is not configured — set PLAID_CLIENT_ID and PLAID_SECRET on the API",
            status_code=503,
        )
    api_base, plaid_env = resolve_plaid_api_base(settings=settings, params={"plaid_env": "sandbox"})
    # Force sandbox for connect until production activation is separately signed off.
    if plaid_env != "sandbox":
        api_base, plaid_env = "https://sandbox.plaid.com", "sandbox"
    body: dict[str, Any] = {
        "client_id": client_id,
        "secret": secret,
        "client_name": "Gravitre",
        "language": "en",
        "country_codes": DEFAULT_COUNTRY_CODES,
        "products": DEFAULT_PRODUCTS,
        "user": {"client_user_id": str(client_user_id)[:128]},
        "redirect_uri": (redirect_uri or DEFAULT_REDIRECT_URI).strip(),
    }
    data = _plaid_post(api_base, "/link/token/create", body)
    return {
        "link_token": data.get("link_token"),
        "expiration": data.get("expiration"),
        "request_id": data.get("request_id"),
        "api_base": api_base,
        "plaid_env": plaid_env,
        "redirect_uri": body["redirect_uri"],
    }


def exchange_public_token(
    settings: Settings,
    *,
    public_token: str,
) -> dict[str, Any]:
    client_id, secret = plaid_platform_credentials(settings)
    if not client_id or not secret:
        raise PlaidLinkError(
            "Plaid is not configured — set PLAID_CLIENT_ID and PLAID_SECRET on the API",
            status_code=503,
        )
    api_base, plaid_env = resolve_plaid_api_base(settings=settings, params={"plaid_env": "sandbox"})
    if plaid_env != "sandbox":
        api_base, plaid_env = "https://sandbox.plaid.com", "sandbox"
    data = _plaid_post(
        api_base,
        "/item/public_token/exchange",
        {
            "client_id": client_id,
            "secret": secret,
            "public_token": public_token.strip(),
        },
    )
    return {
        "access_token": data.get("access_token"),
        "item_id": data.get("item_id"),
        "request_id": data.get("request_id"),
        "api_base": api_base,
        "plaid_env": plaid_env,
    }


def persist_plaid_connection(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    settings: Settings,
    access_token: str,
    item_id: str | None,
    plaid_env: str,
    connector_id: str | None = None,
    connector_name: str | None = None,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Store access_token on an existing or newly created plaid connector row."""
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, str(connector_id), environment_name=environment_name)
    if not conn:
        conn = get_connector_by_type(client, org_id, "plaid", environment_name=environment_name)
    if not conn:
        # Fall back to any staged pack scaffold row (needs_connection).
        rows = (
            client.table("connectors")
            .select("id,type,status,config,environment,name")
            .eq("org_id", org_id)
            .eq("type", "plaid")
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if rows.data:
            conn = dict(rows.data[0])

    config_patch = {
        "plaid_env": plaid_env or "sandbox",
        "api_base": "https://sandbox.plaid.com",
        "item_id": item_id,
        "auth_mode": "plaid_link",
        "needs_connection": False,
    }

    if conn:
        cid = str(conn["id"])
        existing_cfg = conn.get("config") if isinstance(conn.get("config"), dict) else {}
        update_connector(
            client,
            org_id,
            cid,
            {**existing_cfg, **config_patch},
            "active",
            environment_name=conn.get("environment") or environment_name,
        )
    else:
        row = {
            "org_id": org_id,
            "name": (connector_name or "plaid-sandbox").strip() or "plaid-sandbox",
            "vendor": "plaid",
            "type": "plaid",
            "description": "Plaid Link (Sandbox)",
            "status": "active",
            "environment": environment_name,
            "config": config_patch,
        }
        _ = user_id  # actor recorded via audit at the route layer
        created = client.table("connectors").insert(row).execute()
        if not created.data:
            raise PlaidLinkError("Failed to create Plaid connector row", status_code=500)
        cid = str(created.data[0]["id"])

    set_secret(client, org_id, cid, "access_token", access_token, settings)
    set_secret(client, org_id, cid, "plaid_access_token", access_token, settings)
    return {"connector_id": cid, "item_id": item_id, "plaid_env": plaid_env or "sandbox"}
