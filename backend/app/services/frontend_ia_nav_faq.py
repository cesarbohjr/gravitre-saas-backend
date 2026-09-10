"""Deterministic answers for consolidated admin IA navigation questions.

Used as an early short-circuit in assistant chat so sidebar FAQ does not
fall into tool loops or paraphrase hub names (Insights vs Intelligence).

These matchers must stay narrow. A substring like "enterprise" plus "where"
is ordinary operator language (Google Ads, CRM, etc.) and must not replace
the live assistant.
"""

from __future__ import annotations

from typing import Any

from app.services.operator_task_intent import looks_like_operator_task

# Long connector/setup prompts are never sidebar FAQs unless they name the nav.
_MAX_FAQ_CHARS_WITHOUT_NAV = 800

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
_ADMIN_IA_TERMS = ("enterprise", "federation", "environments")
_SETTINGS_EXPLICIT = (
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
# Bare "where" / "primary" / "settings" / "admin" are too common in operator tasks.
_NAV_INTENT = (
    "sidebar",
    "navigation",
    "nav item",
    "primary nav",
    "primary hub",
    "app navigation",
    "where do i",
    "where should i",
    "where is",
    "which hub",
    "which primary",
)
_STRONG_NAV = (
    "sidebar",
    "navigation",
    "nav item",
    "primary nav",
    "primary hub",
    "app navigation",
)


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _is_settings_ia_question(text: str) -> bool:
    term_count = sum(1 for term in _ADMIN_IA_TERMS if term in text)
    explicit = _has_any(text, _SETTINGS_EXPLICIT)
    if term_count >= 2 and _has_any(text, _NAV_INTENT):
        return True
    if explicit and _has_any(text, _NAV_INTENT):
        return True
    # Single IA term is allowed only with explicit product-nav vocabulary.
    if term_count >= 1 and _has_any(text, _STRONG_NAV):
        return True
    return False


def match_frontend_ia_nav_faq(message: str) -> dict[str, Any] | None:
    text = (message or "").strip().lower()
    if not text:
        return None
    if len(text) > _MAX_FAQ_CHARS_WITHOUT_NAV and not _has_any(text, _STRONG_NAV):
        return None
    if looks_like_operator_task(text) and not _has_any(text, _STRONG_NAV):
        return None
    # Prefer specific hubs before generic "sidebar" chatter.
    if _has_any(text, _ACTIVITY_HINTS) and _has_any(text, _NAV_INTENT):
        return {
            "hub": "activity",
            "answer": (
                "Open **Activity** (`/activity`) in the primary sidebar. "
                "Completed work lives there; failure alerts are under the **Failures** tab."
            ),
        }
    if _has_any(text, _AGENTS_HINTS) and _has_any(text, _NAV_INTENT):
        return {
            "hub": "agents",
            "answer": (
                "Open **Agents** (`/agents`). Roster, Multi-agent, and Training are "
                "tabs inside that hub — not separate top-level nav items."
            ),
        }
    if _is_settings_ia_question(text):
        return {
            "hub": "settings",
            "answer": (
                "Open **Settings** (`/settings`). Enterprise, Federation, and Environments "
                "are under **Settings → Admin** — not separate primary sidebar items."
            ),
        }
    if _has_any(text, _INTELLIGENCE_HINTS) and _has_any(text, _NAV_INTENT):
        return {
            "hub": "intelligence",
            "answer": (
                "Open **Intelligence** (`/intelligence`). That hub covers operational health/metrics, "
                "ROI reports, learning signals, models, memory, and predictive ops."
            ),
        }
    return None
