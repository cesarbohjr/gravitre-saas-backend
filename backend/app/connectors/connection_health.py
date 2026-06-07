"""Connector connection health (OAuth token validity)."""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.connectors.hubspot_oauth import hubspot_connection_auth_status, normalize_vendor as normalize_hubspot_vendor
from app.connectors.quickbooks_oauth import (
    normalize_vendor as normalize_quickbooks_vendor,
    quickbooks_connection_auth_status,
)
from app.connectors.confluence_oauth import (
    confluence_connection_auth_status,
    normalize_vendor as normalize_confluence_vendor,
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
from app.connectors.slack_oauth import (
    normalize_vendor as normalize_slack_vendor,
    slack_connection_auth_status,
)
from app.connectors.generic_oauth import generic_connection_auth_status
from app.connectors.google_vendor_oauth import (
    GOOGLE_OAUTH_VENDORS,
    google_vendor_connection_auth_status,
    normalize_google_vendor,
)
from app.connectors.oauth_provider_registry import (
    GENERIC_OAUTH_VENDORS,
    normalize_generic_vendor,
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
    if normalize_confluence_vendor(vendor) == "confluence":
        return confluence_connection_auth_status(
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
    google_vendor = normalize_google_vendor(vendor)
    if google_vendor and google_vendor in GOOGLE_OAUTH_VENDORS:
        return google_vendor_connection_auth_status(
            client,
            org_id,
            connector_id,
            google_vendor,
            settings,
            environment_name=environment_name,
        )
    if normalize_slack_vendor(vendor) == "slack":
        return slack_connection_auth_status(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
    generic_vendor = normalize_generic_vendor(vendor)
    if generic_vendor and generic_vendor in GENERIC_OAUTH_VENDORS:
        return generic_connection_auth_status(
            client,
            org_id,
            connector_id,
            settings,
            vendor=generic_vendor,
            environment_name=environment_name,
        )
    return None


def map_auth_status_to_connector_status(auth_status: str | None, current_status: str) -> str:
    if not auth_status:
        return current_status
    if auth_status == "connected":
        return "healthy"
    if auth_status == "pending_auth":
        return "pending_auth"
    if auth_status == "pending_property":
        return "pending_auth"
    if auth_status in {"auth_expired", "misconfigured"}:
        return "error"
    return current_status
