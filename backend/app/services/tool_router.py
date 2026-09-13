"""Phase B — capability-scoped ReAct tool narrowing (3–10 tools per turn)."""
from __future__ import annotations

from typing import Any

from app.capability_ontology.registry import get_capability
from app.capability_ontology.resolver import resolve_capability
from app.capability_ontology.tool_bridge import capability_tool_name

PHASE_B_MAX_TOOLS = 10
PHASE_B_MIN_TOOLS = 3
_DEFAULT_MAX_TOOLS = 28

_RAG_SUPPRESS_INTENTS = frozenset(
    {
        "chitchat",
        "simple_math",
        "general_knowledge",
        "reference_confirm",
        "reference_reject",
    }
)


def react_max_tools_for_classification(classification: dict[str, Any] | None) -> int:
    """Tighter tool budget when a capability route is active."""
    cls = classification if isinstance(classification, dict) else {}
    if cls.get("capability_id"):
        return PHASE_B_MAX_TOOLS
    intent_class = str(cls.get("intent_class") or "").strip().lower()
    if intent_class in _RAG_SUPPRESS_INTENTS:
        return PHASE_B_MIN_TOOLS
    return _DEFAULT_MAX_TOOLS


def _tool_matches_vendor(tool_name: str, vendor: str) -> bool:
    name = str(tool_name or "").strip().lower()
    vendor_key = str(vendor or "").strip().lower()
    if not name or not vendor_key:
        return False
    return name.startswith(f"{vendor_key}.") or vendor_key in name


def narrow_permitted_tools_for_capability(
    permitted_tools: list[str],
    *,
    classification: dict[str, Any] | None,
    connected_integrations: list[str] | None = None,
    max_tools: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Filter registry-permitted tools to capability binding vendors + platform utilities."""
    tools = list(permitted_tools or [])
    cls = classification if isinstance(classification, dict) else {}
    cap_id = str(cls.get("capability_id") or "").strip().lower()
    budget = max_tools if max_tools is not None else react_max_tools_for_classification(cls)

    if not cap_id:
        if len(tools) > budget:
            return tools[:budget], {"toolRouter": "budget_only", "maxTools": budget}
        return tools, {"toolRouter": "unscoped", "maxTools": budget}

    definition = get_capability(cap_id)
    if definition is None:
        return tools, {"toolRouter": "unknown_capability", "capabilityId": cap_id}

    connected = {str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()}
    resolution = resolve_capability(
        cap_id,
        connected_integrations=list(connected),
        query=str(cls.get("_query") or ""),
        classification=cls,
    )
    vendors: set[str] = set()
    if resolution.resolved_vendor:
        vendors.add(resolution.resolved_vendor)
    else:
        for binding in definition.bindings:
            if binding.vendor in connected:
                vendors.add(binding.vendor)

    cap_tool = capability_tool_name(cap_id)
    platform_keep = {
        "web_search",
        "knowledge_base",
        "workflow_runs",
        "schedules_list",
        "agent_status",
    }
    scoped: list[str] = []
    for name in tools:
        lower = str(name).strip().lower()
        if lower == cap_tool or lower in platform_keep:
            scoped.append(name)
            continue
        if vendors and any(_tool_matches_vendor(lower, vendor) for vendor in vendors):
            scoped.append(name)

    if not scoped:
        scoped = [cap_tool] if cap_tool else tools[:budget]
    elif cap_tool not in scoped:
        scoped.insert(0, cap_tool)

    deduped = list(dict.fromkeys(scoped))
    if len(deduped) > budget:
        deduped = deduped[:budget]

    return deduped, {
        "toolRouter": "capability_scoped",
        "capabilityId": cap_id,
        "vendors": sorted(vendors),
        "maxTools": budget,
        "visibleTools": len(deduped),
    }
