"""Shared connector status and environment resolution for UI, chat, and tool execution."""
from __future__ import annotations

# Statuses that mean the integration is usable for read/write (matches connectors UI normalization).
ACTIVE_CONNECTOR_STATUSES = frozenset({"active", "connected", "syncing", "healthy"})

# Legacy DB default; chat and UI operate in production unless header specifies otherwise.
DEFAULT_ENVIRONMENT = "production"

ENVIRONMENT_ALIASES = {
    "default": "production",
    "prod": "production",
    "stage": "staging",
}


def normalize_environment_name(environment_name: str | None) -> str:
    raw = str(environment_name or DEFAULT_ENVIRONMENT).strip().lower()
    return ENVIRONMENT_ALIASES.get(raw, raw) or DEFAULT_ENVIRONMENT


def connector_environment_candidates(environment_name: str | None) -> list[str]:
    """Query order: requested env, production, legacy default (deduped)."""
    primary = normalize_environment_name(environment_name)
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in (primary, "production", "default"):
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def is_connector_usable(status: str | None) -> bool:
    return str(status or "").lower() in ACTIVE_CONNECTOR_STATUSES
