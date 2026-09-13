"""Canonical connector identity resolution from natural language.

Single source of truth for connector ids, aliases, display names, and categories.
All resolution callers should use this module — not parallel alias tables.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Iterator

# Aliases too generic to attribute a mention to one vendor.
GENERIC_CONNECTOR_ALIASES = frozenset(
    {
        "email",
        "crm",
        "design",
        "analytics",
        "wiki",
        "spreadsheet",
        "sheet",
        "drive",
        "calendar",
        "teams",
        "support ticket",
        "support tickets",
        "pull request",
        "pull requests",
        "ads campaign",
    }
)

# Base alias table (formerly INTEGRATION_ALIASES in chat_connector_models).
_BASE_ALIASES: dict[str, tuple[str, ...]] = {
    "hubspot": ("hubspot", "crm"),
    "salesforce": ("salesforce", "sfdc"),
    "slack": ("slack",),
    "zendesk": ("zendesk", "support ticket", "support tickets"),
    "github": ("github", "gh", "pull request", "pull requests"),
    "jira": ("jira", "atlassian ticket"),
    "confluence": ("confluence", "wiki page", "wiki"),
    "monday": ("monday", "monday.com", "monday board"),
    "google_drive": ("google drive", "drive", "gdrive", "google sheet"),
    "google_sheets": ("google sheets", "spreadsheet", "sheet"),
    "google_docs": ("google docs", "google doc"),
    "google_calendar": ("google calendar", "calendar event", "calendar"),
    "gmail": ("gmail", "email", "send email", "send mail"),
    "microsoft365": ("microsoft 365", "m365", "outlook", "microsoft graph", "teams"),
    "microsoft_teams": ("teams", "microsoft teams"),
    "intercom": ("intercom",),
    "clickup": ("clickup", "click up"),
    "pipedrive": ("pipedrive",),
    "canva": ("canva", "design"),
    "figma": ("figma",),
    "stripe": ("stripe",),
    "pagerduty": ("pagerduty", "on-call", "oncall"),
    "quickbooks": ("quickbooks", "qbo", "quickbooks online"),
    "asana": ("asana",),
    "apollo": ("apollo", "apollo.io"),
    "clay": ("clay",),
    "notion": ("notion",),
    "odoo": ("odoo",),
    "netsuite": ("netsuite",),
    "workday": ("workday",),
    "constant_contact": ("constant contact",),
    "google_analytics": ("google analytics", "ga4", "analytics", "ga", "google analytics 4", "googleanalytics", "website analytics", "google website analytics"),
    "google_search_console": ("google search console", "search console", "gsc"),
    "google_ads": ("google ads", "googleads", "adwords", "ad words", "ads campaign"),
    "twilio": ("twilio", "sms", "text message"),
    "sendgrid": ("sendgrid", "send grid"),
    "airtable": ("airtable",),
    "linear": ("linear", "linear.app"),
    "mailchimp": ("mailchimp",),
    "freshdesk": ("freshdesk",),
    "gorgias": ("gorgias",),
}

_PROVIDER_BY_CONNECTOR: dict[str, str] = {
    "google_analytics": "Google",
    "google_search_console": "Google",
    "google_ads": "Google",
    "google_drive": "Google",
    "google_sheets": "Google",
    "google_docs": "Google",
    "google_calendar": "Google",
    "gmail": "Google",
    "hubspot": "HubSpot",
    "salesforce": "Salesforce",
    "slack": "Slack",
    "github": "GitHub",
    "microsoft365": "Microsoft",
    "microsoft_teams": "Microsoft",
    "quickbooks": "Intuit",
    "zendesk": "Zendesk",
}

_CATEGORY_BY_CONNECTOR: dict[str, str] = {
    "google_analytics": "web_analytics",
    "google_search_console": "organic_search",
    "google_ads": "paid_ads",
    "hubspot": "crm",
    "salesforce": "crm",
    "slack": "communication",
    "github": "devtools",
    "microsoft365": "productivity",
    "quickbooks": "finance",
    "gmail": "communication",
    "google_calendar": "calendar",
}

_RESOURCE_TYPES: dict[str, tuple[str, ...]] = {
    "google_analytics": ("property",),
    "google_search_console": ("site",),
    "google_ads": ("customer",),
    "hubspot": ("connection", "portal"),
    "salesforce": ("connection", "org"),
    "slack": ("connection", "workspace"),
    "github": ("connection", "org"),
    "microsoft365": ("connection", "tenant"),
    "quickbooks": ("connection", "company"),
}

_PHASE_A_CONNECTORS = frozenset(
    {
        "google_analytics",
        "google_search_console",
        "google_ads",
        "hubspot",
        "salesforce",
        "slack",
        "github",
        "microsoft365",
        "quickbooks",
    }
)


@dataclass(frozen=True)
class ConnectorDefinition:
    canonical_id: str
    display_name: str
    provider: str
    aliases: tuple[str, ...]
    abbreviations: tuple[str, ...]
    category: str
    resource_types: tuple[str, ...]

    @property
    def capabilities(self) -> tuple[str, ...]:
        """Placeholder for Phase B capability binding."""
        return ()


def _display_name(connector_id: str) -> str:
    from app.capability_ontology.conversational_grace import vendor_display_label

    return vendor_display_label(connector_id)


def _abbreviations_for(connector_id: str, aliases: tuple[str, ...]) -> tuple[str, ...]:
    abbrevs: list[str] = []
    for alias in aliases:
        cleaned = alias.strip()
        if not cleaned:
            continue
        if len(cleaned) <= 5 and cleaned.isalpha() and cleaned.lower() == cleaned:
            abbrevs.append(cleaned)
        if cleaned.upper() in {"GA4", "GSC", "QBO", "SFDC", "MS365", "GH"}:
            abbrevs.append(cleaned.upper())
    known = {
        "google_analytics": ("ga", "ga4"),
        "google_search_console": ("gsc",),
        "quickbooks": ("qbo",),
        "salesforce": ("sfdc",),
        "github": ("gh",),
        "microsoft365": ("m365", "ms365"),
    }
    for item in known.get(connector_id, ()):
        if item not in abbrevs:
            abbrevs.append(item)
    return tuple(dict.fromkeys(abbrevs))


@lru_cache(maxsize=1)
def connector_definitions() -> dict[str, ConnectorDefinition]:
    out: dict[str, ConnectorDefinition] = {}
    for connector_id in sorted(_BASE_ALIASES.keys()):
        aliases = _dedupe_aliases(connector_id, _BASE_ALIASES[connector_id])
        out[connector_id] = ConnectorDefinition(
            canonical_id=connector_id,
            display_name=_display_name(connector_id),
            provider=_PROVIDER_BY_CONNECTOR.get(connector_id, connector_id.replace("_", " ").title()),
            aliases=aliases,
            abbreviations=_abbreviations_for(connector_id, aliases),
            category=_CATEGORY_BY_CONNECTOR.get(connector_id, "integration"),
            resource_types=_RESOURCE_TYPES.get(connector_id, ("connection",)),
        )
    return out


def _dedupe_aliases(connector_id: str, aliases: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for alias in (connector_id.replace("_", " "), connector_id) + tuple(aliases):
        normalized = str(alias or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


@lru_cache(maxsize=1)
def integration_aliases_dict() -> dict[str, tuple[str, ...]]:
    """Backward-compatible alias map for legacy callers during migration."""
    return {
        connector_id: definition.aliases
        for connector_id, definition in connector_definitions().items()
    }


def get_connector_aliases(connector_id: str) -> tuple[str, ...]:
    definition = connector_definitions().get(str(connector_id or "").strip().lower())
    if definition is None:
        cid = str(connector_id or "").strip().lower()
        return (cid.replace("_", " "), cid) if cid else ()
    return definition.aliases


def iter_integration_alias_items() -> Iterator[tuple[str, tuple[str, ...]]]:
    for connector_id, definition in connector_definitions().items():
        yield connector_id, definition.aliases


@lru_cache(maxsize=1)
def _all_alias_needles() -> tuple[tuple[str, str, int], ...]:
    rows: list[tuple[str, str, int]] = []
    for connector_id, definition in connector_definitions().items():
        seen: set[str] = set()
        for alias in definition.aliases:
            if alias in seen:
                continue
            seen.add(alias)
            rows.append((connector_id, alias, len(alias)))
    rows.sort(key=lambda item: item[2], reverse=True)
    return tuple(rows)


def resolve_connector_from_text(
    text: str,
    *,
    exclude_generic: bool = True,
) -> str | None:
    lowered = (text or "").lower()
    if not lowered.strip():
        return None
    for connector_id, alias, _score in _all_alias_needles():
        if exclude_generic and alias in GENERIC_CONNECTOR_ALIASES:
            continue
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return connector_id
    return None


def resolve_all_connectors_from_text(
    text: str,
    *,
    exclude_generic: bool = True,
) -> list[str]:
    lowered = (text or "").lower()
    found: list[str] = []
    for connector_id, alias, _score in _all_alias_needles():
        if connector_id in found:
            continue
        if exclude_generic and alias in GENERIC_CONNECTOR_ALIASES:
            continue
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            found.append(connector_id)
    return found


def connector_display_name(connector_id: str) -> str:
    definition = connector_definitions().get(str(connector_id or "").strip().lower())
    if definition is not None:
        return definition.display_name
    return _display_name(connector_id)


def connector_definition(connector_id: str) -> ConnectorDefinition | None:
    return connector_definitions().get(str(connector_id or "").strip().lower())


def is_phase_a_connector(connector_id: str) -> bool:
    return str(connector_id or "").strip().lower() in _PHASE_A_CONNECTORS


def is_analytics_family_connector(connector_id: str) -> bool:
    return connector_id in {"google_analytics", "google_search_console", "google_ads"}


def mentions_analytics_traffic_language(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered.strip():
        return False
    traffic_markers = (
        r"\bwebsite\s+traffic\b",
        r"\bweb\s+traffic\b",
        r"\btraffic\b",
        r"\bvisitors?\b",
        r"\bsessions?\b",
        r"\bpage\s*views?\b",
        r"\banalytics\b",
        r"\bperformance\b",
    )
    return any(re.search(pattern, lowered) for pattern in traffic_markers)


def mentions_website_performance_language(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered.strip():
        return False
    patterns = (
        r"\bhow\s+is\s+(?:my\s+)?website\s+doing\b",
        r"\bwebsite\s+(?:doing|performance|stats?)\b",
        r"\bhow\s+(?:is|are)\s+(?:my\s+)?(?:site|website)\b",
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def connected_analytics_vendors(connected: Iterable[str] | None) -> list[str]:
    allowed = {str(item).strip().lower() for item in (connected or []) if str(item).strip()}
    order = ("google_analytics", "google_search_console", "google_ads")
    return [vendor for vendor in order if vendor in allowed]


def resolve_analytics_capabilities_for_message(
    message: str,
    *,
    connected_integrations: list[str] | None,
) -> list[str]:
    """Identify analytics-family connectors relevant to a website-performance ask."""
    connected = connected_analytics_vendors(connected_integrations)
    if not connected:
        return []
    explicit = resolve_all_connectors_from_text(message)
    if explicit:
        return [vendor for vendor in explicit if vendor in connected]
    if mentions_analytics_traffic_language(message) or mentions_website_performance_language(message):
        return connected
    return []
