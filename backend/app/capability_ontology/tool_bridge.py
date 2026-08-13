"""Bridge capability ontology into the existing tool narrowing + invoke pipeline."""
from __future__ import annotations

from typing import Any

from app.capability_ontology.registry import CAPABILITY_REGISTRY, CapabilityDefinition
from app.capability_ontology.resolver import CapabilityResolution, resolve_capability
from app.connectors.action_catalog.registry import get_action_spec
from app.connectors.action_catalog.tool_aliases import catalog_tool_is_implemented
from app.services.tool_service import list_registered_actions

CAPABILITY_TOOL_PREFIX = "capability__"


def capability_id_from_tool_name(tool_name: str) -> str | None:
    name = str(tool_name or "").strip().lower()
    if not name.startswith(CAPABILITY_TOOL_PREFIX):
        return None
    body = name.removeprefix(CAPABILITY_TOOL_PREFIX)
    return ".".join(part for part in body.split("__") if part)


def capability_tool_name(capability_id: str) -> str:
    return CAPABILITY_TOOL_PREFIX + str(capability_id or "").strip().lower().replace(".", "__")


def is_capability_tool_name(tool_name: str) -> bool:
    return str(tool_name or "").strip().lower().startswith(CAPABILITY_TOOL_PREFIX)


def _capability_available(definition: CapabilityDefinition, connected: set[str]) -> bool:
    registered = set(list_registered_actions())
    for binding in definition.bindings:
        if binding.vendor not in connected:
            continue
        if catalog_tool_is_implemented(binding.action_key, registered):
            return True
    return False


def build_capability_tool_definition(
    definition: CapabilityDefinition,
    *,
    connected_integrations: list[str],
) -> dict[str, Any] | None:
    connected = {str(c).strip().lower() for c in connected_integrations if str(c).strip()}
    if not _capability_available(definition, connected):
        return None
    name = capability_tool_name(definition.capability_id)
    desc = (
        f"{definition.description} "
        f"(capability: {definition.capability_id}; resolves to the customer's connected vendor at invoke time)."
    )
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc[:240],
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_vendor": {
                        "type": "string",
                        "description": "Optional vendor hint when multiple connectors implement this capability.",
                    },
                },
            },
        },
        "integration": "capability",
        "capability_id": definition.capability_id,
        "gravitre_capability": True,
        "capability_kind": definition.kind,
    }


def inject_capability_tools(
    tools: list[dict[str, Any]],
    *,
    connected_integrations: list[str] | None,
    query: str = "",
    classification: dict[str, Any] | None = None,
    max_capabilities: int = 8,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Append capability-layer tools after narrowing — resolution happens at invoke."""
    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    if not connected:
        return tools, {"capabilityToolsInjected": 0}

    injected: list[dict[str, Any]] = []
    for cap_id, definition in CAPABILITY_REGISTRY.items():
        tool_def = build_capability_tool_definition(definition, connected_integrations=connected)
        if not tool_def:
            continue
        resolution = resolve_capability(
            cap_id,
            connected_integrations=connected,
            query=query,
            classification=classification,
        )
        if resolution.ambiguous:
            tool_def["function"]["description"] = (
                tool_def["function"]["description"]
                + " Multiple connectors available — specify preferred_vendor or name the system in your request."
            )[:280]
        injected.append(tool_def)
        if len(injected) >= max_capabilities:
            break

    if not injected:
        return tools, {"capabilityToolsInjected": 0}

    existing_names = {
        str((t.get("function") or {}).get("name") or t.get("name") or "").strip().lower()
        for t in tools
    }
    merged = list(tools)
    for tool_def in injected:
        name = str((tool_def.get("function") or {}).get("name") or "").strip().lower()
        if name and name not in existing_names:
            merged.append(tool_def)
            existing_names.add(name)

    return merged, {
        "capabilityToolsInjected": len(injected),
        "capabilityIds": [t.get("capability_id") for t in injected],
    }


def resolve_capability_tool_execution(
    tool_name: str,
    *,
    connected_integrations: list[str] | None,
    query: str = "",
    classification: dict[str, Any] | None = None,
    args: dict[str, Any] | None = None,
) -> CapabilityResolution:
    cap_id = capability_id_from_tool_name(tool_name)
    if not cap_id:
        return CapabilityResolution(
            capability_id="",
            resolved_action=None,
            resolved_vendor=None,
            ambiguous=False,
            candidates=(),
            reason="not_capability_tool",
            resolution_method="none",
        )
    return resolve_capability(
        cap_id,
        connected_integrations=connected_integrations,
        query=query,
        classification=classification,
        args=args,
    )


def schema_for_resolved_action(action_key: str) -> dict[str, Any]:
    spec = get_action_spec(action_key)
    if spec and isinstance(spec.input_schema, dict) and spec.input_schema:
        return spec.input_schema
    return {"type": "object", "properties": {}}
