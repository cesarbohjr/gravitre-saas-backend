"""Connector action catalog registry — v1/v2/v3 tools and demo workflows."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.connectors.action_catalog.models import ActionSpec, VendorCatalogSpec
from app.connectors.action_catalog.vendor_definitions import VENDOR_DEFINITIONS


def _implemented_tools() -> set[str]:
    from app.services.tool_service import list_registered_actions

    return set(list_registered_actions())


@lru_cache(maxsize=1)
def get_vendor_catalog() -> dict[str, VendorCatalogSpec]:
    return {spec.vendor: spec for spec in VENDOR_DEFINITIONS}


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
