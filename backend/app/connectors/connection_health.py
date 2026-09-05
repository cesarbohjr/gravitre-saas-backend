"""Connector connection health (OAuth token validity)."""
from __future__ import annotations

import time
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
from app.connectors.odoo import odoo_connection_auth_status
from app.connectors.oauth_provider_registry import (
    GENERIC_OAUTH_VENDORS,
    normalize_generic_vendor,
)


# Voice latency (2026-09-05): each connector vendor check below is a blocking,
# synchronous network round-trip (e.g. slack_connection_auth_status opens its
# own httpx.Client per call). resolve_connector_auth_status has multiple,
# uncoordinated callers within a single turn (org_context_service,
# assistant_tools.tool_connector_status, connector_snapshot_cache, ...), none
# of which share a cache with each other. Live evidence: one consequential
# voice turn re-checked the SAME Slack connector 5 times in ~10s (each a real
# network call, "slack_auth_test_failed" x5), which alone accounted for most
# of a ~14s response. OAuth token validity does not flip within seconds, so a
# short shared TTL here is safe for every caller (voice AND text) and kills
# the redundant re-checks without reducing real staleness detection below
# ~20s. Any caller can still bypass with force_refresh=True if it genuinely
# needs a fresh check (e.g. right after a reconnect flow).
_AUTH_STATUS_CACHE_TTL_SECONDS = 20.0
_auth_status_cache: dict[str, tuple[float, str | None]] = {}


def resolve_connector_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    vendor: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
    validate_remote: bool = False,
    force_refresh: bool = False,
) -> str | None:
    """Return auth status for OAuth connectors, or None if not applicable."""
    cache_key = f"{org_id}:{connector_id}:{vendor}:{environment_name or ''}:{validate_remote}"
    if not force_refresh:
        cached = _auth_status_cache.get(cache_key)
        if cached is not None and (time.monotonic() - cached[0]) < _AUTH_STATUS_CACHE_TTL_SECONDS:
            return cached[1]
    result = _resolve_connector_auth_status_uncached(
        client,
        org_id,
        connector_id,
        vendor,
        settings,
        environment_name=environment_name,
        validate_remote=validate_remote,
    )
    _auth_status_cache[cache_key] = (time.monotonic(), result)
    return result


def _resolve_connector_auth_status_uncached(
    client: Any,
    org_id: str,
    connector_id: str,
    vendor: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
    validate_remote: bool = False,
) -> str | None:
    if vendor == "odoo":
        return odoo_connection_auth_status(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
    if vendor == "apollo":
        from app.services.apollo_tools import apollo_connection_auth_status

        return apollo_connection_auth_status(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
    if normalize_hubspot_vendor(vendor) == "hubspot":
        return hubspot_connection_auth_status(
            client,
            org_id,
            connector_id,
            settings,
            environment_name=environment_name,
            validate_remote=validate_remote,
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
    if auth_status == "pending_site":
        return "pending_auth"
    if auth_status == "pending_customer":
        return "pending_auth"
    if auth_status in {"auth_expired", "misconfigured"}:
        return "error"
    return current_status


def resolve_display_connector_status(raw_status: str, auth_status: str | None) -> str:
    """Match connectors UI status labels (connected / error / disconnected / syncing)."""
    auth = auth_status or ""
    normalized = str(raw_status or "disconnected").lower()
    # Explicit pending/disconnected row status wins over leftover token health. Otherwise
    # soft-delete + OAuth start can resurrect a row as pending_auth while stale oauth_tokens
    # still resolve as auth=connected and the UI lies.
    if normalized in {"pending_auth", "pending", "disconnected", "inactive"}:
        if auth in {"auth_expired", "misconfigured"}:
            return "error"
        return "disconnected"
    if auth == "connected":
        return "connected"
    if auth in {"auth_expired", "misconfigured"}:
        return "error"
    if auth in {"pending_auth", "pending_property", "pending_site", "pending_customer"}:
        return "disconnected"

    if normalized in {"connected", "syncing", "error", "disconnected"}:
        return normalized
    if normalized in {"healthy", "active"}:
        return "connected"
    if normalized == "error":
        return "error"
    return "disconnected"


def connector_is_connected_for_assistant(raw_status: str, auth_status: str | None) -> bool:
    display = resolve_display_connector_status(raw_status, auth_status)
    return display in {"connected", "syncing"}
