"""Connector action catalog registry — v1/v2/v3 tools and demo workflows."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.connectors.action_catalog.models import ActionSpec, VendorCatalogSpec
from app.connectors.action_catalog.vendor_definitions import VENDOR_DEFINITIONS
from app.connectors.action_catalog.extensions import merge_catalog_extensions


def _implemented_tools() -> set[str]:
    from app.services.tool_service import list_registered_actions

    return set(list_registered_actions())


@lru_cache(maxsize=1)
def get_vendor_catalog() -> dict[str, VendorCatalogSpec]:
    base = {spec.vendor: spec for spec in VENDOR_DEFINITIONS}
    return merge_catalog_extensions(base)


def list_catalog_vendors() -> list[str]:
    return sorted(get_vendor_catalog().keys())


def get_vendor_spec(vendor: str) -> VendorCatalogSpec | None:
    return get_vendor_catalog().get(vendor.lower().strip())


def get_vendor_catalog_dict(vendor: str) -> dict[str, Any] | None:
    spec = get_vendor_spec(vendor)
    if not spec:
        return None
    return spec.to_dict(implemented_tools=_implemented_tools())


def list_full_catalog() -> dict[str, Any]:
    implemented = _implemented_tools()
    vendors = [
        spec.to_dict(implemented_tools=implemented)
        for spec in get_vendor_catalog().values()
    ]
    return {
        "vendors": vendors,
        "vendorCount": len(vendors),
        "tierLabels": {
            "v1": "Read",
            "v2": "Write",
            "v3": "Advanced",
            "v4": "Orchestration",
        },
    }


def source_action_destination_coverage_report() -> dict[str, Any]:
    """Coverage summary for SOURCE/ACTION/DESTINATION connector capability axis."""
    from app.connectors.action_catalog.integration_taxonomy import (
        get_integration_class,
        source_action_destination_profile,
    )

    rows: list[dict[str, Any]] = []
    source_count = 0
    action_count = 0
    destination_count = 0
    for vendor, spec in sorted(get_vendor_catalog().items()):
        sad = source_action_destination_profile(vendor, actions=list(spec.all_actions()))
        if sad["source"]:
            source_count += 1
        if sad["action"]:
            action_count += 1
        if sad["destination"]:
            destination_count += 1
        rows.append(
            {
                "vendor": vendor,
                "integrationClass": get_integration_class(vendor),
                "source": sad["source"],
                "action": sad["action"],
                "destination": sad["destination"],
                "reason": sad["reason"],
            }
        )

    total = len(rows) or 1
    return {
        "summary": {
            "vendorCount": len(rows),
            "sourceCount": source_count,
            "actionCount": action_count,
            "destinationCount": destination_count,
            "sourceCoveragePct": round((source_count / total) * 100, 2),
            "actionCoveragePct": round((action_count / total) * 100, 2),
            "destinationCoveragePct": round((destination_count / total) * 100, 2),
        },
        "rows": rows,
    }


def connector_actions_for_goal_service() -> dict[str, list[str]]:
    """Flatten v1–v3 catalog actions for workflow goal planning."""
    result: dict[str, list[str]] = {}
    for vendor, spec in get_vendor_catalog().items():
        actions: list[str] = []
        for action in spec.all_actions():
            suffix = action.id.split(".", 1)[-1]
            actions.append(suffix.replace(".", "_"))
        result[vendor] = actions
    return result


def catalog_scopes_by_tool() -> dict[str, list[str]]:
    """Map invoke_tool action keys → permission scopes for agent_tool_permissions."""
    scopes: dict[str, list[str]] = {}
    for spec in get_vendor_catalog().values():
        for action in spec.all_actions():
            tool_key = action.id
            scopes[tool_key] = list(action.scopes)
    return scopes


def demo_workflows_for_vendor(vendor: str) -> list[dict[str, Any]]:
    spec = get_vendor_spec(vendor)
    if not spec:
        return []
    return [wf.to_dict(vendor=spec.vendor) for wf in spec.demo_workflows]


def read_tools_for_vendor(vendor: str) -> list[str]:
    spec = get_vendor_spec(vendor)
    if not spec:
        return []
    return [action.id for action in spec.v1]


def all_catalog_action_specs() -> list[ActionSpec]:
    specs: list[ActionSpec] = []
    for vendor_spec in get_vendor_catalog().values():
        specs.extend(vendor_spec.all_actions())
    return specs


def get_action_spec(action_key: str) -> ActionSpec | None:
    """Lookup a catalog ActionSpec by canonical tool key."""
    key = action_key.strip().lower()
    if "." not in key:
        return None
    vendor = key.split(".", 1)[0]
    spec = get_vendor_spec(vendor)
    if not spec:
        return None
    for action in spec.all_actions():
        if action.id.lower() == key:
            return action
    return None
