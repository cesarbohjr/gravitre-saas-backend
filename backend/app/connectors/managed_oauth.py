"""In-memory token adapter for explicitly reauthorized native OAuth accounts."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.connectors.nango_client import _auth_headers, _base_url
from app.connectors.nango_registry import NANGO_FALLBACK_REGISTRY
from app.core.safe_dict import safe_normalize_stored_dict


def managed_oauth_row(client: Any, org_id: str, connector_id: str, *, environment_name: str | None = None) -> dict | None:
    query = (client.table("connectors").select("id,org_id,vendor,type,environment,status,config")
             .eq("org_id", org_id).eq("id", connector_id).is_("deleted_at", "null"))
    if environment_name:
        query = query.eq("environment", environment_name)
    rows = query.limit(1).execute().data
    if not rows or not isinstance(rows[0], dict):
        return None
    row = rows[0]
    if safe_normalize_stored_dict(row, key="config").get("auth_provider") != "managed":
        return None
    return row


def managed_oauth_tokens(client: Any, org_id: str, connector_id: str, settings: Any, *, environment_name: str | None = None) -> dict | None:
    row = managed_oauth_row(client, org_id, connector_id, environment_name=environment_name)
    if row is None:
        return None
    config = safe_normalize_stored_dict(row, key="config")
    vendor = str(row.get("vendor") or row.get("type") or "")
    spec = NANGO_FALLBACK_REGISTRY.get(vendor)
    connection_id = str(config.get("managed_connection_id") or "")
    if (not spec or config.get("managed_integration_id") != spec.integration_id or not connection_id
            or row.get("status") not in {"active", "healthy", "connected", "syncing"}):
        raise ValueError("Managed authorization is incomplete; reconnect this account")
    try:
        with httpx.Client(timeout=20) as http:
            response = http.get(f"{_base_url(settings)}/connections/{quote(connection_id, safe='')}",
                                headers=_auth_headers(settings), params={"provider_config_key": spec.integration_id})
        response.raise_for_status()
        body = response.json()
        if (not isinstance(body, dict) or body.get("connection_id") != connection_id
                or body.get("provider_config_key") != spec.integration_id or body.get("error") or body.get("errors")):
            raise ValueError("Invalid managed connection")
        credentials = body.get("credentials")
        token = credentials.get("access_token") if isinstance(credentials, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise ValueError("No access token")
        # Nango refreshes the token. Never store it or pass its refresh token to
        # native OAuth refreshers; existing governed executors receive it in memory.
        return {"access_token": token}
    except (httpx.HTTPError, ValueError) as exc:
        raise ValueError("Managed authorization unavailable; reconnect this account") from exc
