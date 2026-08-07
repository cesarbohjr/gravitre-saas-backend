"""Unified Google product OAuth (Gravitre OAuth app) — GA4, Calendar, Gmail, Drive, Docs, Sheets, Search Console."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.connectors.google_oauth_common import (
    GOOGLE_AUTHORIZE_URL,
    google_oauth_configured,
    google_oauth_credentials,
    google_oauth_redirect_uri,
)
from app.connectors.google_oauth_tokens import exchange_google_code, refresh_google_token
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

TOKEN_REFRESH_BUFFER_SEC = 300

GOOGLE_OAUTH_VENDORS = frozenset(
    {
        "google_analytics",
        "google_calendar",
        "gmail",
        "google_drive",
        "google_docs",
        "google_sheets",
        "google_search_console",
        "google_ads",
    }
)

_VENDOR_ALIASES: dict[str, str] = {
    "googleanalytics": "google_analytics",
    "google_analytics": "google_analytics",
    "ga4": "google_analytics",
    "ga": "google_analytics",
    "googlecalendar": "google_calendar",
    "google_calendar": "google_calendar",
    "calendar": "google_calendar",
    "gmail": "gmail",
    "googledrive": "google_drive",
    "google_drive": "google_drive",
    "drive": "google_drive",
    "googledocs": "google_docs",
    "google_docs": "google_docs",
    "docs": "google_docs",
    "googlesheets": "google_sheets",
    "google_sheets": "google_sheets",
    "sheets": "google_sheets",
    "googlesearchconsole": "google_search_console",
    "google_search_console": "google_search_console",
    "searchconsole": "google_search_console",
    "gsc": "google_search_console",
    "webmasters": "google_search_console",
    "googleads": "google_ads",
    "google_ads": "google_ads",
    "adwords": "google_ads",
    "ads": "google_ads",
}

_VENDOR_SCOPES: dict[str, str] = {
    "google_analytics": "https://www.googleapis.com/auth/analytics.readonly https://www.googleapis.com/auth/analytics.edit",
    "google_calendar": "https://www.googleapis.com/auth/calendar",
    "gmail": "https://www.googleapis.com/auth/gmail.modify",
    "google_drive": "https://www.googleapis.com/auth/drive",
    "google_docs": "https://www.googleapis.com/auth/documents",
    "google_sheets": "https://www.googleapis.com/auth/spreadsheets",
    "google_search_console": "https://www.googleapis.com/auth/webmasters.readonly",
    # Modern Google Ads API scope (legacy AdWords API is sunset).
    "google_ads": "https://www.googleapis.com/auth/adwords",
}

VENDOR_DOCS: dict[str, str] = {
    "google_analytics": "https://developers.google.com/analytics/devguides/config/admin/v1",
    "google_calendar": "https://developers.google.com/calendar/api/guides/overview",
    "gmail": "https://developers.google.com/gmail/api",
    "google_drive": "https://developers.google.com/drive/api",
    "google_docs": "https://developers.google.com/docs/api",
    "google_sheets": "https://developers.google.com/sheets/api",
    "google_search_console": "https://developers.google.com/webmaster-tools/v1/api_reference_index",
    "google_ads": "https://developers.google.com/google-ads/api/docs/start",
}


def normalize_google_vendor(provider: str) -> str | None:
    raw = provider.strip().lower()
    compact = raw.replace(" ", "").replace("-", "").replace("_", "")
    if compact in _VENDOR_ALIASES:
        return _VENDOR_ALIASES[compact]
    underscored = raw.replace(" ", "_").replace("-", "_")
    if underscored in _VENDOR_ALIASES:
        return _VENDOR_ALIASES[underscored]
    return None


def google_vendor_redirect_uri(settings: Settings, vendor: str) -> str:
    return google_oauth_redirect_uri(settings, vendor)


def google_vendor_authorize_url(vendor: str, client_id: str, redirect_uri: str, state: str) -> str:
    scope = _VENDOR_SCOPES[vendor]
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": scope,
            "redirect_uri": redirect_uri,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
    )
    return f"{GOOGLE_AUTHORIZE_URL}?{query}"


def refresh_google_vendor_tokens_if_needed(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = google_oauth_credentials(settings, env)
    if not client_id or not client_secret:
        return None, "Google OAuth is not configured on the server"
    if not settings.connector_secrets_encryption_key:
        return None, "Connector secrets encryption is not configured"

    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens or not tokens.get("access_token"):
        return None, "OAuth not completed"

    refresh_token = tokens.get("refresh_token")
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and refresh_token:
        try:
            tokens = refresh_google_token(
                str(refresh_token),
                client_id=client_id,
                client_secret=client_secret,
            )
            store_oauth_tokens(client, org_id, connector_id, tokens, settings)
            logger.info("google_token_refreshed org_id=%s connector_id=%s", org_id, connector_id)
        except httpx.HTTPError as exc:
            mark_connector_oauth_failure(client, org_id, connector_id, "Token refresh failed")
            return None, f"Token refresh failed: {exc}"

    return tokens, None


def ensure_google_vendor_session(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str | None, str | None]:
    tokens, err = refresh_google_vendor_tokens_if_needed(
        client, org_id, connector_id, settings, environment_name=environment_name
    )
    if err or not tokens:
        return None, err or "OAuth not completed"
    token = str(tokens.get("access_token") or "")
    if not token:
        return None, "OAuth not completed"
    return token, None


def _connector_property_id(client: Any, org_id: str, connector_id: str) -> str | None:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((row.data or [{}])[0], key="config")
    property_id = (config.get("property_id") or config.get("propertyId") or "").strip()
    return property_id or None


def _connector_site_url(client: Any, org_id: str, connector_id: str) -> str | None:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((row.data or [{}])[0], key="config")
    site_url = (config.get("site_url") or config.get("siteUrl") or "").strip()
    return site_url or None


def complete_google_vendor_oauth_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    vendor: str,
    code: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
    reconnect: bool = False,
) -> bool:
    """Complete OAuth. Returns True when GA4/GSC auto-linked a single property/site."""
    env = environment_name or _connector_environment(client, org_id, connector_id)
    client_id, client_secret = google_oauth_credentials(settings, env)
    if not client_id or not client_secret:
        raise ValueError("Google OAuth is not configured")

    tokens = exchange_google_code(
        code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=google_vendor_redirect_uri(settings, vendor),
    )
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
    config["oauth_provider"] = vendor
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()

    access = str(tokens.get("access_token") or "")
    if not access:
        return vendor not in {"google_analytics", "google_search_console", "google_ads"}

    if vendor == "google_analytics":
        from app.connectors.google_analytics import list_ga4_properties
        from app.connectors.google_analytics_oauth import link_ga4_property

        properties = list_ga4_properties(access)
        ga4_only = [
            p
            for p in properties
            if p.get("property_type") in {None, "PROPERTY_TYPE_ORDINARY", "PROPERTY_TYPE_UNSPECIFIED"}
        ]
        candidates = ga4_only or properties
        if len(candidates) == 1:
            prop = candidates[0]
            link_ga4_property(
                client,
                org_id,
                connector_id,
                property_id=str(prop["property_id"]),
                property_name=prop.get("display_name"),
                property_resource=prop.get("property_resource"),
            )
            return True
        return False

    if vendor == "google_search_console":
        from app.connectors.google_search_console import list_gsc_sites
        from app.connectors.google_search_console_oauth import link_gsc_site

        sites = list_gsc_sites(access)
        if len(sites) == 1:
            site = sites[0]
            link_gsc_site(
                client,
                org_id,
                connector_id,
                site_url=str(site["site_url"]),
                permission_level=site.get("permission_level"),
            )
            return True
        return False

    if vendor == "google_ads":
        from app.connectors.google_ads import list_accessible_customers
        from app.connectors.google_ads_oauth import link_google_ads_customer

        developer_token = (getattr(settings, "google_ads_developer_token", None) or "").strip()
        if not developer_token:
            # OAuth succeeded; customer link waits until developer token is configured.
            return False
        try:
            customers = list_accessible_customers(access, developer_token=developer_token)
        except Exception:  # noqa: BLE001
            return False
        if len(customers) == 1:
            link_google_ads_customer(
                client,
                org_id,
                connector_id,
                customer_id=str(customers[0]["customer_id"]),
            )
            return True
        return False

    return True


def google_vendor_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    vendor: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    env = environment_name or _connector_environment(client, org_id, connector_id)
    if not google_oauth_configured(settings, env):
        return "misconfigured"
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return "pending_auth"
    if token_needs_refresh(tokens, TOKEN_REFRESH_BUFFER_SEC) and not tokens.get("refresh_token"):
        return "auth_expired"
    token, err = ensure_google_vendor_session(
        client, org_id, connector_id, settings, environment_name=env
    )
    if err or not token:
        return "auth_expired"
    if vendor == "google_analytics" and not _connector_property_id(client, org_id, connector_id):
        return "pending_property"
    if vendor == "google_search_console" and not _connector_site_url(client, org_id, connector_id):
        return "pending_site"
    if vendor == "google_ads":
        if not (getattr(settings, "google_ads_developer_token", None) or "").strip():
            return "misconfigured"
        if not _connector_ads_customer_id(client, org_id, connector_id):
            return "pending_customer"
    return "connected"


def _connector_ads_customer_id(client: Any, org_id: str, connector_id: str) -> str | None:
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((row.data or [{}])[0], key="config")
    cid = str(config.get("customer_id") or config.get("customerId") or "").strip().replace("-", "")
    return cid or None
