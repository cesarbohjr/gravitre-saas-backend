"""Connector action execution matrix — catalog vs invoke_tool vs chat exposure."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal

from app.connectors.action_catalog.registry import get_vendor_catalog
from app.connectors.action_catalog.tool_aliases import (
    catalog_tool_is_implemented,
    registry_keys_for_catalog_tool,
    resolve_registry_action,
)
from app.services.catalog_write_authority import catalog_action_requires_write_approval
from app.services.tool_service import list_registered_actions

ImplementationStatus = Literal[
    "executable",
    "not_implemented",
    "catalog_only",
    "requires_approval",
    "blocked_missing_scope",
    "blocked_missing_credentials",
]

PRIORITY_CONNECTORS: frozenset[str] = frozenset(
    {
        "monday",
        "google_drive",
        "google_sheets",
        "google_docs",
        "google_calendar",
        "gmail",
        "jira",
        "confluence",
        "salesforce",
        "hubspot",
        "slack",
        "zendesk",
        "intercom",
        "github",
        "canva",
        "figma",
        "microsoft365",
        "microsoft_teams",
        "clickup",
        "netsuite",
        "workday",
        "odoo",
        "constant_contact",
        "pipedrive",
        "google_analytics",
        "google_ads",
        "linkedin",
        "asana",
        "notion",
        "quickbooks",
        "stripe",
        "pagerduty",
        "apollo",
    }
)


@dataclass(frozen=True)
class ConnectorActionMatrixEntry:
    connector_id: str
    action_key: str
    display_name: str
    description: str
    action_type: str
    kind: str
    destructive: bool
    requires_approval: bool
    required_scopes: tuple[str, ...]
    implementation_status: str
    registry_key: str
    tool_registry_key: str
    invoke_tool_handler: str
    chat_executable: bool
    chat_phrases: tuple[str, ...] = field(default_factory=tuple)
    fallback_behavior: str = "not_supported"
    tier: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "connectorId": self.connector_id,
            "actionKey": self.action_key,
            "displayName": self.display_name,
            "description": self.description,
            "actionType": self.action_type,
            "kind": self.kind,
            "destructive": self.destructive,
            "requiresApproval": self.requires_approval,
            "requiredScopes": list(self.required_scopes),
            "implementationStatus": self.implementation_status,
            "toolRegistryKey": self.tool_registry_key,
            "invokeToolHandler": self.invoke_tool_handler,
            "chatExecutable": self.chat_executable,
            "chatPhrases": list(self.chat_phrases),
            "fallbackBehavior": self.fallback_behavior,
            "tier": self.tier,
        }


def _tool_registry_key(vendor: str, action_key: str) -> str:
    suffix = action_key.split(".", 1)[-1] if "." in action_key else action_key
    normalized = suffix.replace(".", "_")
    return f"{vendor}_{normalized}"


def _chat_phrases(vendor: str, action_key: str, display_name: str, kind: str) -> tuple[str, ...]:
    suffix = action_key.split(".", 1)[-1] if "." in action_key else action_key
    resource, _, verb = suffix.partition(".")
    phrases = [
        display_name.lower(),
        f"{vendor} {display_name}".lower(),
        f"{verb} {resource}".replace("_", " "),
        f"{resource} {verb}".replace("_", " "),
        suffix.replace(".", " "),
        action_key.replace(".", " "),
    ]
    if kind == "read":
        phrases.extend([f"search {resource}", f"list {resource}", f"find {resource}", f"get {resource}"])
    else:
        phrases.extend([f"create {resource}", f"update {resource}", f"send {resource}", f"post {resource}"])
    return tuple(dict.fromkeys(p.strip() for p in phrases if p.strip()))


def _implementation_status(
    catalog_key: str,
    registered: set[str],
    *,
    kind: str,
    destructive: bool,
    requires_approval: bool,
    scopes: tuple[str, ...] = (),
) -> str:
    if not catalog_tool_is_implemented(catalog_key, registered):
        return "not_implemented"
    if catalog_action_requires_write_approval(
        kind=kind,
        destructive=destructive,
        requires_approval=requires_approval,
        scopes=scopes,
    ):
        return "requires_approval"
    return "executable"


@lru_cache(maxsize=1)
def build_connector_execution_matrix() -> tuple[ConnectorActionMatrixEntry, ...]:
    registered = set(list_registered_actions())
    entries: list[ConnectorActionMatrixEntry] = []
    for vendor, spec in get_vendor_catalog().items():
        for action in spec.all_actions():
            catalog_key = action.id if "." in action.id and action.id.startswith(f"{vendor}.") else f"{vendor}.{action.id}"
            registry_key = resolve_registry_action(catalog_key, registered)
            implemented = registry_key in registered
            impl_status = (
                _implementation_status(
                    catalog_key,
                    registered,
                    kind=action.kind,
                    destructive=action.destructive,
                    requires_approval=action.requires_approval,
                    scopes=action.scopes,
                )
                if implemented
                else "not_implemented"
            )
            tool_key = _tool_registry_key(vendor, catalog_key)
            chat_executable = implemented
            needs_approval = catalog_action_requires_write_approval(
                kind=action.kind,
                destructive=action.destructive,
                requires_approval=action.requires_approval,
                scopes=action.scopes,
            )
            entries.append(
                ConnectorActionMatrixEntry(
                    connector_id=vendor,
                    action_key=catalog_key,
                    display_name=action.name,
                    description=action.description,
                    action_type=action.kind,
                    kind=action.kind,
                    destructive=action.destructive,
                    requires_approval=needs_approval,
                    required_scopes=action.scopes,
                    implementation_status=impl_status,
                    registry_key=registry_key,
                    tool_registry_key=tool_key,
                    invoke_tool_handler=registry_key if implemented else "",
                    chat_executable=chat_executable,
                    chat_phrases=_chat_phrases(vendor, catalog_key, action.name, action.kind),
                    fallback_behavior="not_supported" if not implemented else "invoke_tool",
                    tier=action.tier,
                )
            )
    return tuple(entries)


def get_execution_matrix() -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in build_connector_execution_matrix()]


def get_matrix_entry(connector_id: str, action_key: str) -> ConnectorActionMatrixEntry | None:
    normalized = action_key if action_key.startswith(f"{connector_id}.") else f"{connector_id}.{action_key}"
    for entry in build_connector_execution_matrix():
        if entry.connector_id == connector_id and entry.action_key == normalized:
            return entry
    return None


def matrix_summary() -> dict[str, Any]:
    entries = build_connector_execution_matrix()
    by_vendor: dict[str, dict[str, int]] = {}
    for entry in entries:
        bucket = by_vendor.setdefault(entry.connector_id, {"executable": 0, "total": 0, "chat": 0})
        bucket["total"] += 1
        if entry.implementation_status != "not_implemented":
            bucket["executable"] += 1
        if entry.chat_executable:
            bucket["chat"] += 1
    return {
        "totalActions": len(entries),
        "executableActions": sum(1 for e in entries if e.implementation_status != "not_implemented"),
        "chatExecutableActions": sum(1 for e in entries if e.chat_executable),
        "priorityConnectors": sorted(PRIORITY_CONNECTORS),
        "byVendor": by_vendor,
    }


def chat_executable_entries(
    *,
    connected_integrations: list[str] | None = None,
) -> list[ConnectorActionMatrixEntry]:
    connected = {c.lower() for c in (connected_integrations or [])}
    result: list[ConnectorActionMatrixEntry] = []
    for entry in build_connector_execution_matrix():
        if not entry.chat_executable:
            continue
        if connected and entry.connector_id not in connected:
            continue
        result.append(entry)
    return result


def skip_reason_for_entry(
    entry: ConnectorActionMatrixEntry | None,
    *,
    connected: bool,
) -> str | None:
    from app.services.gravitre_voice import format_operator_message

    if entry is None:
        return format_operator_message(
            "no_executable_action",
            confidence_register="blocked",
            allow_humor=False,
        )
    if not connected:
        return format_operator_message(
            "connector_connect_to_run",
            integration=entry.connector_id,
            confidence_register="blocked",
            allow_humor=False,
        )
    if entry.implementation_status == "not_implemented":
        return (
            f"{entry.display_name} is cataloged but not implemented in invoke_tool yet "
            f"({entry.action_key})."
        )
    return None
