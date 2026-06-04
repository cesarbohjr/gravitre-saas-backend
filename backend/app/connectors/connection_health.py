"""Connector connection health (OAuth token validity)."""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.connectors.hubspot_oauth import hubspot_connection_auth_status, normalize_vendor


def resolve_connector_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    vendor: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str | None:
    """Return auth status for OAuth connectors, or None if not applicable."""
    v = normalize_vendor(vendor)
    if v == "hubspot":
        return hubspot_connection_auth_status(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
    return None


def map_auth_status_to_connector_status(auth_status: str | None, current_status: str) -> str:
    if not auth_status:
        return current_status
    if auth_status == "connected":
        return "healthy"
    if auth_status == "pending_auth":
        return "pending_auth"
    if auth_status in {"auth_expired", "misconfigured"}:
        return "error"
    return current_status
