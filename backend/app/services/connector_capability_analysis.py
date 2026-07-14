"""Catalog-driven connector capability analysis for fallback and registry checks."""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.registry import get_action_spec, get_vendor_spec
from app.connectors.action_catalog.tool_aliases import catalog_tool_is_implemented
from app.services.connector_execution_matrix import build_connector_execution_matrix
from app.services.tool_service import list_registered_actions

# Substring patterns matched against catalog action ids (vendor.resource.verb).
LIST_CAPABILITY_CHECKS: dict[str, tuple[str, ...]] = {
    "create_list": ("lists.create", "list.create", "contact_lists.create"),
    "add_to_list": ("lists.add", "lists.members.add", "sequences.add"),
    "saved_search": ("saved_searches.create", "segments.create"),
    "search_people": ("people.search", "contacts.search"),
    "search_companies": ("organizations.search", "companies.search"),
    "create_contact": ("contacts.create",),
}

CAPABILITY_DISPLAY_LABELS: dict[str, str] = {
    "create_list": "Can create list?",
    "add_to_list": "Can add contacts to existing list/sequence?",
    "saved_search": "Can create saved search?",
    "search_people": "Can search people?",
    "search_companies": "Can search companies?",
    "create_contact": "Can create contact?",
}

LIST_FALLBACK_CAPABILITIES: tuple[str, ...] = (
    "create_list",
    "add_to_list",
    "saved_search",
)


def parse_action_keys(available_actions: list[str]) -> list[str]:
    """Extract catalog/registry keys from chat action labels."""
    keys: list[str] = []
    for item in available_actions:
        text = item.strip()
        if not text:
            continue
        if " — " in text:
            keys.append(text.split(" — ", 1)[0].strip())
        elif " - " in text:
            keys.append(text.split(" - ", 1)[0].strip())
        else:
            keys.append(text)
    return keys


def implemented_action_keys_for_vendor(vendor: str) -> list[str]:
    """Return implemented catalog action keys for a vendor."""
    return [
        entry.action_key
        for entry in build_connector_execution_matrix()
        if entry.connector_id == vendor and entry.implementation_status != "not_implemented"
    ]


def catalog_action_keys_for_vendor(vendor: str) -> list[str]:
    spec = get_vendor_spec(vendor)
    if not spec:
        return []
    return [action.id for action in spec.all_actions()]


def action_matches_capability(action_key: str, capability: str) -> bool:
    patterns = LIST_CAPABILITY_CHECKS.get(capability, ())
    lowered = action_key.lower()
    return any(pattern in lowered for pattern in patterns)


def declared_capabilities(vendor: str) -> set[str]:
    """Capabilities with at least one matching catalog action id for this vendor."""
    declared: set[str] = set()
    for action_key in catalog_action_keys_for_vendor(vendor):
        for capability in LIST_CAPABILITY_CHECKS:
            if action_matches_capability(action_key, capability):
                declared.add(capability)
    return declared


def normalize_action_key(integration: str, key: str) -> str:
    """Prefix short matrix labels (e.g. people.search) with the vendor id."""
    text = key.strip()
    if text.startswith(f"{integration}."):
        return text
    if get_action_spec(text):
        return text
    candidate = f"{integration}.{text}"
    if get_action_spec(candidate):
        return candidate
    return candidate if "." in text else text


def analyze_capability_gaps(
    integration: str,
    available_actions: list[str] | None = None,
) -> dict[str, bool]:
    """Map capabilities to whether implemented catalog actions exist for the vendor."""
    if available_actions:
        action_keys = [
            normalize_action_key(integration, key)
            for key in parse_action_keys(available_actions)
        ]
        return {
            capability: any(
                action_matches_capability(key, capability) for key in action_keys
            )
            for capability in LIST_CAPABILITY_CHECKS
        }

    registered = set(list_registered_actions())
    action_keys = implemented_action_keys_for_vendor(integration)
    result: dict[str, bool] = {}
    for capability in LIST_CAPABILITY_CHECKS:
        matching = [key for key in action_keys if action_matches_capability(key, capability)]
        if not matching:
            result[capability] = False
            continue
        result[capability] = any(catalog_tool_is_implemented(key, registered) for key in matching)
    return result


def find_catalog_action_for_capability(integration: str, capability: str) -> str | None:
    """Return the first catalog action id that declares a capability, implemented or not."""
    for action_key in catalog_action_keys_for_vendor(integration):
        if action_matches_capability(action_key, capability):
            if "." in action_key and action_key.split(".", 1)[0] == integration:
                return action_key
            return f"{integration}.{action_key}" if "." not in action_key else action_key
    return None


def resolve_missing_action(integration: str, capability: str) -> str:
    """Best catalog action id for a missing capability (for operator next-step hints)."""
    found = find_catalog_action_for_capability(integration, capability)
    if found:
        return found
    patterns = LIST_CAPABILITY_CHECKS.get(capability, ())
    suffix = patterns[0] if patterns else capability.replace("_", ".")
    return suffix if suffix.startswith(f"{integration}.") else f"{integration}.{suffix}"


def capability_check_lines(
    gaps: dict[str, bool],
    *,
    vendor: str,
    capabilities: tuple[str, ...] = LIST_FALLBACK_CAPABILITIES,
    plan_limited_discovery: bool | None = None,
) -> list[str]:
    declared = declared_capabilities(vendor)
    lines: list[str] = []
    vendor_l = str(vendor or "").strip().lower()
    for capability in capabilities:
        if capability not in declared:
            continue
        label = CAPABILITY_DISPLAY_LABELS.get(capability, capability.replace("_", " "))
        available = bool(gaps.get(capability))
        line = f"- {label} {'yes' if available else 'no'}"
        if vendor_l == "apollo" and capability in {"search_people", "search_companies"}:
            from app.connectors.apollo_discovery_capability import APOLLO_DISCOVERY_REQUIRES

            if plan_limited_discovery or not available:
                line = f"- {label} no — requires: {APOLLO_DISCOVERY_REQUIRES}"
            else:
                line = f"- {label} yes — requires: {APOLLO_DISCOVERY_REQUIRES} (tenant plan must include search)"
        lines.append(line)
    return lines


def build_capability_summary(
    *,
    integration: str,
    vendor_label: str,
    gaps: dict[str, bool],
    focus_capability: str = "create_list",
) -> str:
    if gaps.get("search_people") or gaps.get("search_companies"):
        summary = f"I can search {vendor_label} people/companies"
    elif gaps.get("create_contact"):
        summary = f"I can create {vendor_label} contacts"
    else:
        summary = f"The {vendor_label} connector is connected"

    if focus_capability == "create_list" and not gaps.get("create_list"):
        if "create_list" in declared_capabilities(integration):
            summary += f", but I cannot create {vendor_label} lists yet."
        else:
            summary += f", but list creation is not cataloged for {vendor_label} yet."
    return summary
