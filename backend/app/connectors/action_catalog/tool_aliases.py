"""Map catalog action IDs to invoke_tool registry keys (Google short prefixes + Outlook)."""
from __future__ import annotations

# Catalog vendor prefix → tool_service registry prefix
REGISTRY_VENDOR_PREFIX_ALIASES: dict[str, str] = {
    "google_analytics": "analytics",
    "google_search_console": "searchconsole",
    "google_calendar": "calendar",
    "google_drive": "drive",
    "google_docs": "docs",
    "google_sheets": "sheets",
    "google_ads": "googleads",
}

# Exact catalog action → registry action when suffixes differ (STA-337 Outlook honesty).
# Do not use vendor-prefix alias for outlook → microsoft365; suffixes do not match.
REGISTRY_ACTION_ALIASES: dict[str, str] = {
    "outlook.messages.send": "microsoft365.mail.send",
    "outlook.messages.list": "microsoft365.mail.messages.list",
    "outlook.batch.send": "microsoft365.batch.mail",
}


def registry_keys_for_catalog_tool(catalog_key: str) -> frozenset[str]:
    """Return catalog tool key plus known registry aliases for implemented checks."""
    keys: set[str] = {catalog_key}
    exact = REGISTRY_ACTION_ALIASES.get(catalog_key)
    if exact:
        keys.add(exact)
    vendor, _, rest = catalog_key.partition(".")
    alias_vendor = REGISTRY_VENDOR_PREFIX_ALIASES.get(vendor)
    if alias_vendor and rest:
        keys.add(f"{alias_vendor}.{rest}")
    return frozenset(keys)


def catalog_tool_is_implemented(catalog_key: str, implemented: set[str]) -> bool:
    return bool(registry_keys_for_catalog_tool(catalog_key) & implemented)


def resolve_registry_action(action: str, registered: set[str]) -> str:
    """Map catalog tool key to invoke_tool registry key when aliases exist.

    ``google_ads.*`` → prefer dedicated ``googleads.*`` when both are registered
    (catalog-HTTP must not win). Other Google vendors keep their long-form
    dedicated handlers (e.g. ``google_drive.search_files``).
    Exact ``outlook.*`` remaps prefer microsoft365 executors (STA-337).
    F8 short↔canonical id aliases keep legacy callers working.
    """
    from app.connectors.action_catalog.action_id_aliases import (
        ACTION_ID_ALIASES,
        resolve_canonical_action_id,
    )

    exact = REGISTRY_ACTION_ALIASES.get(action)
    if exact and exact in registered:
        return exact

    # Prefer currently-registered short ids; accept canonical when present.
    if action in registered:
        # Fall through to google prefix logic only when needed below.
        pass
    else:
        canonical = resolve_canonical_action_id(action)
        if canonical in registered:
            return canonical
        for alias, canon in ACTION_ID_ALIASES.items():
            if action == canon and alias in registered:
                return alias

    vendor, _, rest = action.partition(".")
    alias_vendor = REGISTRY_VENDOR_PREFIX_ALIASES.get(vendor)
    candidate = f"{alias_vendor}.{rest}" if alias_vendor and rest else None

    if vendor == "google_ads" and candidate and candidate in registered:
        return candidate
    if action in registered:
        return action
    if candidate and candidate in registered:
        return candidate
    if exact:
        return exact
    return action
