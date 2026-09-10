"""Drop competing-vendor knowledge hits when another catalog vendor is in-scope.

Live failure: after HubSpot list-create rejected parameters, "Use standard default
fields" ranked Salesforce Trailhead / Siebel articles. The model treated those
hits as HubSpot schema. The same shape recurs wherever two catalog vendors share
business language (Gmail/Outlook, Slack/Teams, Jira/Linear, …).

Rule: if a hit is about vendor V, V is not the subject of this turn, and a
sibling in V's competing family *is* in-scope (mentioned or connected), drop it.
Neutral hits (no catalog-vendor marker) stay.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Iterable, Mapping

from app.services.chat_connector_models import INTEGRATION_ALIASES

# Markers too generic to attribute a knowledge hit to one vendor.
_GENERIC_MARKERS = frozenset(
    {
        "crm",
        "email",
        "wiki",
        "wiki page",
        "spreadsheet",
        "sheet",
        "google sheet",
        "design",
        "analytics",
        "calendar",
        "calendar event",
        "drive",
        "teams",
        "sms",
        "text message",
        "on-call",
        "oncall",
        "support ticket",
        "support tickets",
        "pull request",
        "pull requests",
        "ads campaign",
    }
)

# Vendors that share overlapping operator language. A hit about one member must
# not rank as schema for another member that is in-scope this turn.
_COMPETING_FAMILIES: tuple[frozenset[str], ...] = (
    frozenset({"hubspot", "salesforce", "siebel", "dynamics", "pipedrive", "apollo", "odoo"}),
    frozenset({"gmail", "microsoft365", "sendgrid", "mailchimp", "constant_contact"}),
    frozenset({"slack", "microsoft_teams", "intercom"}),
    frozenset(
        {"zendesk", "jira", "freshdesk", "gorgias", "linear", "asana", "clickup", "monday"}
    ),
    frozenset({"confluence", "notion", "google_docs", "google_drive"}),
    frozenset({"google_ads", "google_analytics"}),
)

# Distinctive extra tokens that are not catalog ids.
_EXTRA_MARKERS: dict[str, tuple[str, ...]] = {
    "salesforce": ("sfdc", "trailhead", "sobject"),
    "siebel": ("siebel",),
    "dynamics": ("dynamics 365", "microsoft dynamics", "ms dynamics"),
    "microsoft365": ("outlook", "microsoft 365", "m365", "microsoft graph"),
    "microsoft_teams": ("microsoft teams",),
    "google_analytics": ("ga4", "google analytics"),
    "google_ads": ("google ads", "adwords", "ad words"),
    "apollo": ("apollo.io",),
}

_DEFAULT_FILL_FOLLOWUP = re.compile(
    r"^(?:please\s+|just\s+|ok[,.]?\s+|okay[,.]?\s+)*"
    r"(?:use|apply|go\s+with|stick\s+with|keep)\s+"
    r"(?:the\s+)?"
    r"(?:standard\s+)?"
    r"(?:default(?:s|\s+fields?)?|standard\s+fields?)"
    r"(?:\s+please)?"
    r"[.!]*$",
    re.I,
)


def is_connector_default_fill_followup(message: str) -> bool:
    """True for imperative 'use the defaults' replies — not knowledge questions."""
    text = (message or "").strip()
    if not text or text.endswith("?"):
        return False
    return bool(_DEFAULT_FILL_FOLLOWUP.match(text))


def _normalize_connected(connected: Iterable[str] | None) -> set[str]:
    return {str(item).strip().lower() for item in (connected or []) if str(item).strip()}


def _blob(hit: Mapping[str, Any]) -> str:
    parts = [
        hit.get("title"),
        hit.get("source"),
        hit.get("citation"),
        hit.get("url"),
        hit.get("href"),
        hit.get("web_link"),
        hit.get("publisher"),
        hit.get("content"),
        hit.get("snippet"),
        hit.get("excerpt"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


@lru_cache(maxsize=1)
def _vendor_markers() -> dict[str, tuple[str, ...]]:
    markers: dict[str, list[str]] = {}
    catalog: tuple[str, ...] = ()
    try:
        from app.connectors.action_catalog.registry import list_catalog_vendors

        catalog = tuple(list_catalog_vendors())
    except Exception:  # noqa: BLE001
        catalog = ()

    vendors = set(catalog)
    for family in _COMPETING_FAMILIES:
        vendors.update(family)
    vendors.update(_EXTRA_MARKERS)

    for vendor in sorted(vendors):
        found = {vendor, vendor.replace("_", " ")}
        for alias in INTEGRATION_ALIASES.get(vendor, ()):
            token = str(alias).strip().lower()
            if token and token not in _GENERIC_MARKERS:
                found.add(token)
        for extra in _EXTRA_MARKERS.get(vendor, ()):
            found.add(extra)
        markers[vendor] = tuple(sorted(found, key=len, reverse=True))
    return markers


def _family_of(vendor: str) -> frozenset[str]:
    key = (vendor or "").strip().lower()
    for family in _COMPETING_FAMILIES:
        if key in family:
            return family
    return frozenset({key} if key else ())


def catalog_vendors_mentioned(text: str) -> set[str]:
    blob = (text or "").lower()
    if not blob:
        return set()
    found: set[str] = set()
    for vendor, markers in _vendor_markers().items():
        if any(marker in blob for marker in markers):
            found.add(vendor)
    return found


# Backward-compatible names used by the first CRM-only tests / call sites.
crm_vendors_mentioned = catalog_vendors_mentioned


def known_catalog_vendors() -> set[str]:
    return set(_vendor_markers())


def connected_catalog_vendors(connected: Iterable[str] | None) -> set[str]:
    connected_set = _normalize_connected(connected)
    known = known_catalog_vendors()
    return {vendor for vendor in connected_set if vendor in known}


connected_crm_vendors = connected_catalog_vendors


def infer_active_catalog_vendors(
    query: str,
    *,
    connected_integrations: Iterable[str] | None = None,
) -> set[str]:
    """Which catalog vendor(s) retrieval should treat as in-scope for this turn."""
    connected = connected_catalog_vendors(connected_integrations)
    mentioned = catalog_vendors_mentioned(query)
    mentioned_connected = mentioned & connected
    if mentioned_connected:
        return mentioned_connected
    if mentioned:
        return mentioned
    if len(connected) == 1:
        return set(connected)
    if is_connector_default_fill_followup(query):
        # Ambiguous "use the defaults" after a write: pick the unique member of
        # the first competing family (CRM, then email, then chat, …).
        for family in _COMPETING_FAMILIES:
            members = connected & family
            if len(members) == 1:
                return set(members)
    return set(connected)


infer_active_crm_vendors = infer_active_catalog_vendors


def _display_vendor(vendor: str) -> str:
    if vendor == "hubspot":
        return "HubSpot"
    if vendor == "microsoft365":
        return "Microsoft 365"
    if vendor == "google_ads":
        return "Google Ads"
    return vendor.replace("_", " ").title()


def bias_retrieval_query_for_connected_crm(
    query: str,
    connected_integrations: Iterable[str] | None,
) -> str:
    """Append the unique in-scope vendor when the query names none."""
    text = (query or "").strip()
    if not text:
        return text
    if catalog_vendors_mentioned(text):
        return text
    active = infer_active_catalog_vendors(text, connected_integrations=connected_integrations)
    if len(active) != 1:
        return text
    return f"{text} {_display_vendor(next(iter(active)))}"


def _should_keep_hit_vendors(
    hit_vendors: set[str],
    *,
    query: str,
    connected_integrations: Iterable[str] | None,
) -> bool:
    if not hit_vendors:
        return True
    mentioned = catalog_vendors_mentioned(query)
    connected = connected_catalog_vendors(connected_integrations)
    in_scope = mentioned or connected
    if not in_scope:
        return True
    # Query named a vendor: keep hits about that vendor; drop sibling-family docs.
    subject = mentioned or infer_active_catalog_vendors(
        query, connected_integrations=connected_integrations
    )
    if hit_vendors & subject:
        return True
    for vendor in hit_vendors:
        family = _family_of(vendor)
        if family & subject and vendor not in subject:
            return False
    return True


def filter_competing_crm_knowledge_hits(
    hits: list[dict[str, Any]] | None,
    *,
    connected_integrations: Iterable[str] | None,
    query: str = "",
) -> list[dict[str, Any]]:
    """Drop sibling-family docs for a vendor that is not the subject of this turn."""
    rows = [dict(hit) for hit in (hits or []) if isinstance(hit, dict)]
    kept: list[dict[str, Any]] = []
    for hit in rows:
        vendors = catalog_vendors_mentioned(_blob(hit))
        if _should_keep_hit_vendors(
            vendors, query=query, connected_integrations=connected_integrations
        ):
            kept.append(hit)
    return kept


def keep_knowledge_text(
    text: str,
    *,
    connected_integrations: Iterable[str] | None,
    query: str = "",
) -> bool:
    """True when a formatted evidence section is in-scope for the active vendor family."""
    return _should_keep_hit_vendors(
        catalog_vendors_mentioned(text),
        query=query,
        connected_integrations=connected_integrations,
    )
