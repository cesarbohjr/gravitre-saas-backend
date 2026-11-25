"""Declared connector dependencies only; never infers or grants tool authority."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

_ALIASES = {
    "googleanalytics": "google_analytics", "ga4": "google_analytics",
    "googleads": "google_ads", "googleadwords": "google_ads",
    "microsoft_365": "microsoft365", "microsoft365": "microsoft365",
    "teams": "microsoft_teams", "google_searchconsole": "google_search_console",
    "searchconsole": "google_search_console",
    "halo": "halo_psa", "halopsa": "halo_psa", "connectwise_psa": "connectwise",
}
_LIST_KEYS = frozenset({
    "systems", "connectors", "required_connectors", "requiredConnectors",
    "required_connector_groups", "optional_connectors", "demo_systems",
    "connector_types", "connectorTypes", "vendors",
})
_VENDOR_KEYS = frozenset({"connectorType", "connector_type", "requires_connector", "vendor"})
_ACTION_KEYS = frozenset({"action", "tool_action", "tool", "actionId", "action_id"})
_TOKEN = re.compile(r"^[a-z][a-z0-9_]*$")


def normalize_dependency(value: str) -> str:
    key = re.sub(r"[\s-]+", "_", value.strip().lower())
    return _ALIASES.get(key, key)


def declared_dependencies(payload: Any, *, action_vendors: set[str] | frozenset[str] = frozenset()) -> dict[str, list[str]]:
    """Extract structured declarations, not prose, URLs, UUIDs or credentials.

    Action prefixes count only when present in the canonical vendor catalog.
    Generic references such as platform/FHIR remain visible for human triage;
    they are not silently replaced with a commercial provider.
    """
    found: dict[str, set[str]] = {}

    def add(value: Any, path: str) -> None:
        if isinstance(value, str):
            key = normalize_dependency(value)
            if _TOKEN.fullmatch(key):
                found.setdefault(key, set()).add(path)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                add(item, f"{path}[{index}]")
        elif isinstance(value, Mapping):
            for key in _VENDOR_KEYS:
                if key in value:
                    add(value[key], f"{path}.{key}")

    def walk(value: Any, path: str) -> None:
        if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
            try:
                walk(json.loads(value), path)
            except (ValueError, RecursionError):
                pass
        elif isinstance(value, Mapping):
            for key, item in value.items():
                child = f"{path}.{key}"
                if key in _LIST_KEYS or key in _VENDOR_KEYS:
                    add(item, child)
                elif key == "connector" and isinstance(item, str):
                    add(item, child)
                elif key in _ACTION_KEYS and isinstance(item, str):
                    vendor, separator, _ = item.partition(".")
                    vendor = normalize_dependency(vendor)
                    if separator and vendor in action_vendors:
                        add(vendor, child)
                elif key in {"actions", "tools"} and isinstance(item, list):
                    for index, action in enumerate(item):
                        if isinstance(action, str):
                            vendor, separator, _ = action.partition(".")
                            vendor = normalize_dependency(vendor)
                            if separator and vendor in action_vendors:
                                add(vendor, f"{child}[{index}]")
                walk(item, child)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(payload, "$")
    return {key: sorted(paths) for key, paths in sorted(found.items())}
