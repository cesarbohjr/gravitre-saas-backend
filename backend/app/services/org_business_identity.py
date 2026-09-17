"""Tenant-scoped business website/timezone for resource binding.

Does not add a customer-facing website field. Reads org settings, verified
branding domain, same-org GSC link, and company knowledge-node attributes
already stored for this org_id.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger(__name__)

_SETTINGS_WEBSITE_KEYS = (
    "website",
    "website_url",
    "websiteUrl",
    "company_website",
    "companyWebsite",
    "primary_website",
    "primaryWebsite",
    "primary_domain",
    "primaryDomain",
    "company_domain",
    "companyDomain",
    "domain",
)
_TZ_KEYS = ("timezone", "time_zone", "timeZone", "tz", "org_timezone")
_SAFE_TLDS = frozenset(
    {
        "app",
        "ai",
        "com",
        "net",
        "org",
        "io",
        "co",
        "us",
        "uk",
        "dev",
        "so",
        "gg",
        "me",
        "info",
        "biz",
        "ca",
        "au",
        "de",
        "fr",
        "in",
        "xyz",
        "edu",
        "gov",
    }
)
_HOST_IN_TEXT = re.compile(
    r"(?i)\b(?:https?://|sc-domain:)?(?:www\.)?("
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+)"
    r"(?:[/:?#]|\b)"
)


def normalize_host(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if raw.startswith("sc-domain:"):
        raw = raw.split(":", 1)[1]
    if "://" not in raw:
        raw = f"https://{raw}"
    host = urlparse(raw).hostname or ""
    if host.startswith("www."):
        host = host[4:]
    if host in {"localhost", "127.0.0.1"}:
        return ""
    return host


def extract_domain_hint_from_message(message: str) -> str:
    """Conservative host from operator text — not a free-form filename match."""
    text = str(message or "")
    for match in _HOST_IN_TEXT.finditer(text):
        host = normalize_host(match.group(1))
        if not host or "." not in host:
            continue
        tld = host.rsplit(".", 1)[-1]
        if tld not in _SAFE_TLDS:
            continue
        if any(ch.isdigit() for ch in tld):
            continue
        return host
    return ""


def _first_str(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _identity(org_id: str, website: str, timezone_name: str, source: str) -> dict[str, Any]:
    host = normalize_host(website)
    return {
        "org_id": str(org_id),
        "website": website if host else "",
        "host": host,
        "timezone": timezone_name or "UTC",
        "source": source if host else "none",
    }


def _load_org_settings_row(client: Any, org_id: str) -> dict[str, Any] | None:
    if client is None or not org_id:
        return None
    try:
        result = (
            client.table("organizations")
            .select("id, settings")
            .eq("id", org_id)
            .limit(1)
            .execute()
        )
        rows = result.data if isinstance(getattr(result, "data", None), list) else []
    except Exception as exc:  # noqa: BLE001
        logger.debug("org_business_identity_settings_skipped org=%s err=%s", org_id, exc)
        return None
    if not rows or not isinstance(rows[0], dict):
        return None
    row = rows[0]
    if str(row.get("id") or "") != str(org_id):
        return None
    return row


def _website_from_settings(settings: dict[str, Any]) -> tuple[str, str, str]:
    website = _first_str(settings, _SETTINGS_WEBSITE_KEYS)
    source = "org_settings" if website else ""
    enterprise = settings.get("enterprise") if isinstance(settings.get("enterprise"), dict) else {}
    branding = enterprise.get("branding") if isinstance(enterprise.get("branding"), dict) else {}
    if not website and branding.get("customDomainVerified") and branding.get("customDomain"):
        website = str(branding.get("customDomain") or "").strip()
        source = "verified_branding_domain"
    timezone_name = _first_str(settings, _TZ_KEYS) or "UTC"
    return website, timezone_name, source


def _website_from_knowledge_nodes(client: Any, org_id: str) -> str:
    try:
        from app.services.org_knowledge_nodes_service import list_knowledge_nodes

        nodes = list_knowledge_nodes(client, org_id, node_type="company", limit=20)
    except Exception as exc:  # noqa: BLE001
        logger.debug("org_business_identity_kg_skipped org=%s err=%s", org_id, exc)
        return ""
    hosts: list[str] = []
    websites: list[str] = []
    for node in nodes:
        if str(node.get("org_id") or "") != str(org_id):
            continue
        attrs = node.get("attributes") if isinstance(node.get("attributes"), dict) else {}
        raw = _first_str(
            {**attrs, "name": str(node.get("name") or "")},
            ("website", "website_url", "websiteUrl", "domain", "url", "name"),
        )
        host = normalize_host(raw)
        if not host:
            continue
        if host not in hosts:
            hosts.append(host)
            websites.append(raw if "://" in raw or "." in raw else f"https://{host}")
    if len(hosts) == 1:
        return websites[0]
    return ""


def _website_from_gsc_config(client: Any, org_id: str, *, environment_name: str) -> str:
    try:
        from app.connectors.repository import get_connector_by_type

        row = get_connector_by_type(
            client, org_id, "google_search_console", environment_name=environment_name
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("org_business_identity_gsc_skipped org=%s err=%s", org_id, exc)
        return ""
    if not isinstance(row, dict):
        return ""
    if str(row.get("org_id") or org_id) != str(org_id):
        return ""
    cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
    return str(cfg.get("site_url") or cfg.get("siteUrl") or "").strip()


def load_org_business_identity(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Return website/host/timezone for this org_id only."""
    empty = _identity(org_id, "", "UTC", "none")
    if not org_id or client is None:
        return empty
    row = _load_org_settings_row(client, org_id)
    settings = row.get("settings") if isinstance(row, dict) and isinstance(row.get("settings"), dict) else {}
    website, timezone_name, source = _website_from_settings(settings)
    if not normalize_host(website):
        website = _website_from_gsc_config(client, org_id, environment_name=environment_name)
        source = "gsc_linked_site" if website else source
    if not normalize_host(website):
        website = _website_from_knowledge_nodes(client, org_id)
        source = "knowledge_node" if website else source
    return _identity(org_id, website, timezone_name, source or "none")


def merge_business_identity(
    *,
    org_id: str,
    context: dict[str, Any] | None,
    user_message: str = "",
    client: Any = None,
    environment_name: str = "production",
) -> dict[str, Any]:
    ctx = context if isinstance(context, dict) else {}
    nested = ctx.get("business_identity") if isinstance(ctx.get("business_identity"), dict) else {}
    website = str(
        nested.get("website")
        or nested.get("domain")
        or ctx.get("company_website")
        or ctx.get("website")
        or ""
    ).strip()
    timezone_name = str(
        nested.get("timezone") or ctx.get("timezone") or ctx.get("org_timezone") or ""
    ).strip()
    source = "conversation_context" if website else "none"
    identity = _identity(org_id, website, timezone_name or "UTC", source)

    message_host = extract_domain_hint_from_message(user_message)
    if message_host:
        return _identity(org_id, message_host, identity["timezone"], "user_message")

    if identity["host"]:
        return identity

    loaded = load_org_business_identity(client, org_id, environment_name=environment_name)
    if timezone_name:
        loaded = {**loaded, "timezone": timezone_name}
    return loaded
