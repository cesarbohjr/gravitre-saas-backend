"""Canonical connector identity resolution from natural language.

Single source of truth for mapping user vocabulary to catalog connector ids.
``INTEGRATION_ALIASES`` remains the base table; this module adds extended
aliases and exposes one deterministic resolver consumed by routing, contextual
understanding, clarification, and business-intent layers.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable

from app.services.chat_connector_models import INTEGRATION_ALIASES

# Aliases too generic to attribute a mention to one vendor (must stay aligned
# with clarification_engine and connected_vendor_knowledge_filter).
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

# Extended aliases not yet folded into INTEGRATION_ALIASES tuples.
EXTRA_CONNECTOR_ALIASES: dict[str, tuple[str, ...]] = {
    "google_analytics": (
        "ga",
        "google analytics 4",
        "googleanalytics",
        "website analytics",
        "google website analytics",
    ),
    "google_search_console": ("gsc", "google search console", "search console"),
    "google_ads": ("adwords", "ad words"),
    "quickbooks": ("qbo", "quickbooks online"),
    "microsoft365": ("ms365", "office 365", "office365"),
    "microsoft_teams": ("ms teams",),
    "google_drive": ("gdrive",),
    "salesforce": ("sfdc",),
}


@lru_cache(maxsize=1)
def _all_alias_needles() -> tuple[tuple[str, str, int], ...]:
    """(connector_id, alias, score) sorted longest alias first for greedy match."""
    rows: list[tuple[str, str, int]] = []
    connector_ids = set(INTEGRATION_ALIASES.keys()) | set(EXTRA_CONNECTOR_ALIASES.keys())
    for connector_id in sorted(connector_ids):
        base_aliases = INTEGRATION_ALIASES.get(connector_id, ())
        merged = tuple(base_aliases) + EXTRA_CONNECTOR_ALIASES.get(connector_id, ())
        needles = (connector_id, connector_id.replace("_", " ")) + merged
        seen: set[str] = set()
        for alias in needles:
            normalized = str(alias or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            rows.append((connector_id, normalized, len(normalized)))
    rows.sort(key=lambda item: item[2], reverse=True)
    return tuple(rows)


def resolve_connector_from_text(
    text: str,
    *,
    exclude_generic: bool = True,
) -> str | None:
    """Return the best-matching catalog connector id mentioned in *text*, if any."""
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
    """All distinct connector ids explicitly mentioned (longest-alias wins per id)."""
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
    from app.capability_ontology.conversational_grace import vendor_display_label

    return vendor_display_label(connector_id)


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


def connected_analytics_vendors(connected: Iterable[str] | None) -> list[str]:
    allowed = {str(item).strip().lower() for item in (connected or []) if str(item).strip()}
    order = ("google_analytics", "google_search_console", "google_ads")
    return [vendor for vendor in order if vendor in allowed]
