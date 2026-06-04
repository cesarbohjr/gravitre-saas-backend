"""Connector connection health (OAuth token validity)."""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.connectors.hubspot_oauth import hubspot_connection_auth_status, normalize_vendor as normalize_hubspot_vendor
from app.connectors.quickbooks_oauth import (
    normalize_vendor as normalize_quickbooks_vendor,
    quickbooks_connection_auth_status,
)
from app.connectors.jira_oauth import (
    jira_connection_auth_status,
    normalize_vendor as normalize_jira_vendor,
)
from app.connectors.pagerduty_oauth import (
    normalize_vendor as normalize_pagerduty_vendor,
    pagerduty_connection_auth_status,
)
from app.connectors.notion_oauth import (
    normalize_vendor as normalize_notion_vendor,
    notion_connection_auth_status,
)
from app.connectors.salesforce_oauth import (
    normalize_vendor as normalize_salesforce_vendor,
    salesforce_connection_auth_status,
)


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
    if normalize_hubspot_vendor(vendor) == "hubspot":
        return hubspot_connection_auth_status(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
    if normalize_salesforce_vendor(vendor) == "salesforce":
        return salesforce_connection_auth_status(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
    if normalize_quickbooks_vendor(vendor) == "quickbooks":
        return quickbooks_connection_auth_status(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
    if normalize_jira_vendor(vendor) == "jira":
        return jira_connection_auth_status(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
    if normalize_pagerduty_vendor(vendor) == "pagerduty":
        return pagerduty_connection_auth_status(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
    if normalize_notion_vendor(vendor) == "notion":
        return notion_connection_auth_status(
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
