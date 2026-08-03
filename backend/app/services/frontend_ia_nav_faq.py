"""Deterministic answers for consolidated admin IA navigation questions.

Used as an early short-circuit in assistant chat so sidebar FAQ does not
fall into tool loops or paraphrase hub names (Insights vs Intelligence).
"""

from __future__ import annotations

from typing import Any


_ACTIVITY_HINTS = (
    "completed work",
    "failure alert",
    "failure alerts",
    "businessoutcome",
    "business outcome",
    "where do i look up completed",
    "workflow work",
    "/activity",
)
_AGENTS_HINTS = (
    "multi-agent",
    "agent training",
    "manage my ai agents",
    "manage my agents",
    "agents hub",
)
_SETTINGS_HINTS = (
    "enterprise",
    "federation",
    "environments",
    "settings → admin",
    "settings admin",
    "under admin",
)
_INTELLIGENCE_HINTS = (
    "operational metrics",
    "roi report",
    "roi reports",
    "learning signals",
    "golden signals",
    "operational health",
    "/intelligence",
)


def match_frontend_ia_nav_faq(message: str) -> dict[str, Any] | None:
    text = (message or "").strip().lower()
    if not text:
        return None
    # Prefer specific hubs before generic "sidebar" chatter.
    if any(h in text for h in _ACTIVITY_HINTS) and (
        "sidebar" in text or "navigation" in text or "primary" in text or "where" in text
    ):
        return {
            "hub": "activity",
            "answer": (
                "Open **Activity** (`/activity`) in the primary sidebar. "
                "Completed work lives there; failure alerts are under the **Failures** tab."
            ),
        }
    if any(h in text for h in _AGENTS_HINTS) and (
        "sidebar" in text or "navigation" in text or "primary" in text or "where" in text
    ):
        return {
            "hub": "agents",
            "answer": (
                "Open **Agents** (`/agents`). Roster, Multi-agent, and Training are "
                "tabs inside that hub — not separate top-level nav items."
            ),
        }
    if any(h in text for h in _SETTINGS_HINTS) and (
        "sidebar" in text
        or "navigation" in text
        or "primary" in text
        or "where" in text
        or "nav item" in text
        or "settings" in text
        or "admin" in text
    ):
        return {
            "hub": "settings",
            "answer": (
                "Open **Settings** (`/settings`). Enterprise, Federation, and Environments "
                "are under **Settings → Admin** — not separate primary sidebar items."
            ),
        }
    if any(h in text for h in _INTELLIGENCE_HINTS) and (
        "sidebar" in text or "navigation" in text or "primary" in text or "where" in text or "hub" in text
    ):
        return {
            "hub": "intelligence",
            "answer": (
                "Open **Intelligence** (`/intelligence`). That hub covers operational health/metrics, "
                "ROI reports, learning signals, models, memory, and predictive ops."
            ),
        }
    return None
