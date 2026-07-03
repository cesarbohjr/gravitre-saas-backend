"""Dynamic chat ToolRegistry specs from the connector execution matrix."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.connectors.action_catalog.tool_aliases import resolve_registry_action
from app.services.connector_execution_matrix import build_connector_execution_matrix
from app.services.tool_registry import AgentToolSpec
from app.services.tool_service import list_registered_actions


def _generic_parameters(kind: str, action_suffix: str) -> dict[str, Any]:
    props: dict[str, Any] = {
        "query": {"type": "string", "description": "Search query or keywords"},
        "limit": {"type": "integer", "description": "Maximum results", "default": 10},
        "connector_id": {"type": "string", "description": "Optional connector instance id"},
        "payload": {"type": "object", "description": "Vendor-specific fields"},
    }
    if "message" in action_suffix or "send" in action_suffix or "post" in action_suffix:
        props.update(
            {
                "channel": {"type": "string"},
                "message": {"type": "string"},
                "text": {"type": "string"},
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            }
        )
    if "item" in action_suffix or "task" in action_suffix:
        props.update(
            {
                "board_id": {"type": "string"},
                "item_name": {"type": "string"},
                "name": {"type": "string"},
                "summary": {"type": "string"},
                "project": {"type": "string"},
            }
        )
    if "ticket" in action_suffix or "issue" in action_suffix:
        props.update(
            {
                "ticket_id": {"type": "string"},
                "issue_id": {"type": "string"},
                "comment": {"type": "string"},
            }
        )
    if "contact" in action_suffix or "lead" in action_suffix or "person" in action_suffix:
        props.update(
            {
                "email": {"type": "string"},
                "firstname": {"type": "string"},
                "lastname": {"type": "string"},
                "properties": {"type": "object"},
            }
        )
    if "deal" in action_suffix or "opportunity" in action_suffix:
        props.update(
            {
                "deal_id": {"type": "string"},
                "stage": {"type": "string"},
                "amount": {"type": "number"},
            }
        )
    if "file" in action_suffix or "drive" in action_suffix:
        props.update(
            {
                "file_id": {"type": "string"},
                "folder_id": {"type": "string"},
                "name": {"type": "string"},
            }
        )
    if kind == "read":
        required: list[str] = []
    else:
        required = []
    return {"type": "object", "properties": props, "required": required}


def _passthrough_mapper(args: dict[str, Any]) -> dict[str, Any]:
    return dict(args or {})


@lru_cache(maxsize=1)
def build_dynamic_chat_tool_specs() -> dict[str, AgentToolSpec]:
    registered = set(list_registered_actions())
    specs: dict[str, AgentToolSpec] = {}
    for entry in build_connector_execution_matrix():
        if entry.implementation_status == "not_implemented":
            continue
        registry_key = resolve_registry_action(entry.action_key, registered)
        if registry_key not in registered:
            continue
        suffix = entry.action_key.split(".", 1)[-1]
        description = (
            f"{entry.display_name}. {entry.description} "
            f"({'read' if entry.kind == 'read' else 'write'} action via {entry.connector_id})."
        )
        specs[entry.tool_registry_key] = AgentToolSpec(
            name=entry.tool_registry_key,
            description=description,
            parameters=_generic_parameters(entry.kind, suffix),
            invoke_action=registry_key,
            integration=entry.connector_id,
            map_params=_passthrough_mapper,
        )
    return specs


def get_dynamic_chat_tool_spec(tool_name: str) -> AgentToolSpec | None:
    return build_dynamic_chat_tool_specs().get(tool_name)
