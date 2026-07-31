"""Map catalog action IDs to invoke_tool registry keys (Google short prefixes)."""
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


def registry_keys_for_catalog_tool(catalog_key: str) -> frozenset[str]:
    """Return catalog tool key plus known registry aliases for implemented checks."""
    keys: set[str] = {catalog_key}
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
    """
    vendor, _, rest = action.partition(".")
    alias_vendor = REGISTRY_VENDOR_PREFIX_ALIASES.get(vendor)
    candidate = f"{alias_vendor}.{rest}" if alias_vendor and rest else None

    if vendor == "google_ads" and candidate and candidate in registered:
        return candidate
    if action in registered:
        return action
    if candidate and candidate in registered:
        return candidate
    return action
