"""Cheap CAN_THIS_ACTION_EXECUTE_NOW gate before model tool_choice.

Vendor/action availability only — not HMAC preflight, not live token probes,
not WRITE inference. Uses the turn's connected snapshot plus optional
unavailable-vendor / registered-action hints already in memory.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.connectors.action_catalog.action_id_resolve import (
    resolve_action_id_from_tool_name,
    resolve_integration_from_tool_name,
)
from app.connectors.action_catalog.tool_aliases import (
    REGISTRY_VENDOR_PREFIX_ALIASES,
    catalog_tool_is_implemented,
)

ALWAYS_EXECUTABLE_VENDORS = frozenset(
    {
        "platform",
        "mcp",
        "browser",
        "webhook",
        "email",
        "capability",
        "knowledge",
    }
)

_ALWAYS_OK_NAME_PREFIXES = (
    "assistant_",
    "web_search",
    "search_web",
    "knowledge_",
    "browser_",
    "mcp_",
    "capability__",
    "workflow_",
    "schedules_",
    "agent_status",
    "connector_status",
    "search_catalog",
)


@dataclass(frozen=True)
class ActionExecuteNow:
    ok: bool
    reason: str
    vendor: str
    action_key: str


def _canonical_vendor(vendor: str) -> str:
    key = str(vendor or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return ""
    try:
        from app.intelligence_packs.shared.auth_mode import canonical_connector_vendor

        return canonical_connector_vendor(key) or key
    except Exception:  # noqa: BLE001
        return key


def vendor_identity_keys(vendor: str) -> frozenset[str]:
    raw = str(vendor or "").strip().lower()
    if not raw:
        return frozenset()
    canon = _canonical_vendor(raw)
    keys: set[str] = {raw, canon}
    for catalog, alias in REGISTRY_VENDOR_PREFIX_ALIASES.items():
        if raw in {catalog, alias} or canon in {catalog, alias}:
            keys.add(catalog)
            keys.add(alias)
    return frozenset(k for k in keys if k)


def _connected_keyset(connected_integrations: list[str] | None) -> set[str]:
    out: set[str] = set()
    for item in connected_integrations or []:
        out |= set(vendor_identity_keys(str(item)))
    return out


def _name_is_always_ok(name: str) -> bool:
    lower = str(name or "").strip().lower()
    if not lower:
        return False
    return any(lower.startswith(prefix) for prefix in _ALWAYS_OK_NAME_PREFIXES)


def resolve_action_and_vendor(
    *,
    action_key: str | None = None,
    tool_name: str | None = None,
    vendor: str | None = None,
    tool: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    """Return (tool_name, action_key, vendor)."""
    row = tool if isinstance(tool, dict) else {}
    fn = row.get("function") if isinstance(row.get("function"), dict) else {}
    name = str(tool_name or fn.get("name") or row.get("name") or "").strip()
    action = str(
        action_key
        or row.get("invoke_action")
        or row.get("action")
        or ""
    ).strip()
    if not action and name:
        action = resolve_action_id_from_tool_name(name)
    explicit_vendor = str(vendor or row.get("integration") or "").strip().lower()
    if explicit_vendor:
        resolved_vendor = explicit_vendor
    elif action and "." in action:
        resolved_vendor = action.split(".", 1)[0].lower()
    elif name:
        resolved_vendor = str(resolve_integration_from_tool_name(name) or "").strip().lower()
    else:
        resolved_vendor = ""
    return name, action, resolved_vendor


def can_this_action_execute_now(
    *,
    action_key: str | None = None,
    tool_name: str | None = None,
    vendor: str | None = None,
    tool: dict[str, Any] | None = None,
    connected_integrations: list[str] | None = None,
    unavailable_vendors: list[str] | None = None,
    registered_actions: set[str] | None = None,
    availability_by_vendor: dict[str, bool] | None = None,
) -> ActionExecuteNow:
    """Return whether attaching this action to the model is currently executable.

    Does not run HMAC preflight or remote OAuth probes.
    """
    name, action, resolved_vendor = resolve_action_and_vendor(
        action_key=action_key,
        tool_name=tool_name,
        vendor=vendor,
        tool=tool,
    )
    if _name_is_always_ok(name) or resolved_vendor in ALWAYS_EXECUTABLE_VENDORS:
        return ActionExecuteNow(True, "always_executable", resolved_vendor or "platform", action)

    vendor_keys = vendor_identity_keys(resolved_vendor)
    unavailable = _connected_keyset(list(unavailable_vendors or []))
    if vendor_keys & unavailable:
        return ActionExecuteNow(False, "vendor_unavailable", resolved_vendor, action)

    if availability_by_vendor:
        for key in vendor_keys:
            if key in availability_by_vendor and not availability_by_vendor[key]:
                return ActionExecuteNow(False, "execution_unavailable", resolved_vendor, action)

    connected = _connected_keyset(connected_integrations)
    if resolved_vendor and not (vendor_keys & connected):
        return ActionExecuteNow(False, "not_connected", resolved_vendor, action)

    if registered_actions is not None and action:
        try:
            from app.connectors.action_catalog.registry import get_action_spec

            spec = get_action_spec(action)
        except Exception:  # noqa: BLE001
            spec = None
        if spec is not None and not catalog_tool_is_implemented(action, registered_actions):
            return ActionExecuteNow(False, "not_registered", resolved_vendor, action)

    return ActionExecuteNow(True, "executable", resolved_vendor, action)


# Audit name (planner/tool router gate before tool_choice).
CAN_THIS_ACTION_EXECUTE_NOW = can_this_action_execute_now


def filter_tools_executable_now(
    tools: list[dict[str, Any]],
    *,
    connected_integrations: list[str] | None,
    unavailable_vendors: list[str] | None = None,
    registered_actions: set[str] | None = None,
    availability_by_vendor: dict[str, bool] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    dropped: list[str] = []
    reasons: dict[str, int] = {}
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        result = can_this_action_execute_now(
            tool=tool,
            connected_integrations=connected_integrations,
            unavailable_vendors=unavailable_vendors,
            registered_actions=registered_actions,
            availability_by_vendor=availability_by_vendor,
        )
        if result.ok:
            kept.append(tool)
            continue
        name = resolve_action_and_vendor(tool=tool)[0] or result.action_key
        dropped.append(name)
        reasons[result.reason] = reasons.get(result.reason, 0) + 1
    return kept, {
        "executeNowDropped": len(dropped),
        "executeNowDropReasons": reasons,
        "executeNowDroppedNames": dropped[:12],
    }


def filter_tool_names_executable_now(
    names: list[str],
    *,
    connected_integrations: list[str] | None,
    unavailable_vendors: list[str] | None = None,
    registered_actions: set[str] | None = None,
    availability_by_vendor: dict[str, bool] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    kept: list[str] = []
    dropped: list[str] = []
    reasons: dict[str, int] = {}
    for name in names or []:
        result = can_this_action_execute_now(
            tool_name=str(name),
            connected_integrations=connected_integrations,
            unavailable_vendors=unavailable_vendors,
            registered_actions=registered_actions,
            availability_by_vendor=availability_by_vendor,
        )
        if result.ok:
            kept.append(name)
            continue
        dropped.append(str(name))
        reasons[result.reason] = reasons.get(result.reason, 0) + 1
    return kept, {
        "executeNowDropped": len(dropped),
        "executeNowDropReasons": reasons,
        "executeNowDroppedNames": dropped[:12],
    }


def unavailable_vendors_from_org_context(org_context: dict[str, Any] | None) -> list[str]:
    """Vendors present on the org snapshot but not execution-available (no extra I/O)."""
    ctx = org_context if isinstance(org_context, dict) else {}
    rows = ctx.get("integrations")
    if not isinstance(rows, list):
        return []
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("executionAvailable") is False:
            vendor = str(row.get("type") or row.get("vendor") or "").strip().lower()
            if vendor:
                out.append(vendor)
    return out
