"""Capability ontology — canonical operator intents resolved to catalog actions."""
from app.capability_ontology.registry import CAPABILITY_REGISTRY, get_capability, list_capability_ids
from app.capability_ontology.resolver import CapabilityResolution, resolve_capability
from app.capability_ontology.tool_bridge import (
    capability_id_from_tool_name,
    capability_tool_name,
    inject_capability_tools,
    is_capability_tool_name,
    resolve_capability_tool_execution,
)

__all__ = [
    "CAPABILITY_REGISTRY",
    "CapabilityResolution",
    "capability_id_from_tool_name",
    "capability_tool_name",
    "get_capability",
    "inject_capability_tools",
    "is_capability_tool_name",
    "list_capability_ids",
    "resolve_capability",
    "resolve_capability_tool_execution",
]
