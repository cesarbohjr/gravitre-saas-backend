"""Health for managed auth; never return or persist provider credentials."""
from __future__ import annotations
from typing import Any
from urllib.parse import quote
import httpx
from app.connectors.nango_client import nango_configured, _auth_headers, _base_url
from app.connectors.nango_registry import get_nango_connector_spec


def managed_auth_status(client: Any, org_id: str, connector_id: str, settings: Any, *, environment_name: str | None, validate_remote: bool = False) -> str:
    if not nango_configured(settings) or not settings.nango_webhook_signing_key.strip():
        return "misconfigured"
    query = (client.table("connectors").select("config, status, vendor, type")
             .eq("org_id", org_id).eq("id", connector_id).is_("deleted_at", "null"))
    if environment_name:
        query = query.eq("environment", environment_name)
    rows = query.limit(1).execute().data
    if not rows:
        return "pending_auth"
    row = rows[0]
    config = row.get("config") if isinstance(row.get("config"), dict) else {}
    spec = get_nango_connector_spec(str(row.get("vendor") or row.get("type") or ""))
    if not spec or config.get("auth_provider") != "managed":
        return "pending_auth"
    connection_id = str(config.get("managed_connection_id") or "").strip()
    if config.get("managed_integration_id") != spec.integration_id:
        return "misconfigured"
    if not connection_id or row.get("status") in {"pending_auth", "needs_connection", "inactive", "disconnected"}:
        return "pending_auth"
    if row.get("status") == "error":
        return "auth_expired"
    if validate_remote:
        try:
            # Nango checks/refreshes credentials. Its response never leaves this function.
            with httpx.Client(timeout=20.0) as http:
                response = http.get(f"{_base_url(settings)}/connections/{quote(connection_id, safe='')}",
                                    headers=_auth_headers(settings), params={"provider_config_key": spec.integration_id})
            if response.status_code in {401, 403, 404, 424}:
                return "auth_expired"
            response.raise_for_status()
            body = response.json()
            if (not isinstance(body, dict) or body.get("error") or body.get("errors")
                    or body.get("connection_id") != connection_id
                    or body.get("provider_config_key") != spec.integration_id):
                return "auth_expired"
        except (httpx.HTTPError, ValueError):
            return "misconfigured"
    return "connected"
