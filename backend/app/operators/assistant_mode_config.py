"""Assistant / agent-chat mode configuration for AgentIntelligence streaming."""
from __future__ import annotations

from typing import Any

# Backend MODE_CONFIG is the single source of truth when callers omit `tools`.
ALL_ASSISTANT_TOOL_NAMES: list[str] = [
    "knowledge_base",
    "agent_status",
    "connector_status",
    "workflow_runs",
    "analytics",
    "search_web",
    "generate_document",
    "run_agent_task",
    "create_workflow",
    "execute_workflow",
    "dependency_impact",
]

# Internal ToolRegistry names for assistant platform tools.
ASSISTANT_TOOL_TO_REGISTRY: dict[str, str | None] = {
    "knowledge_base": None,
    "agent_status": "assistant_agent_status",
    "connector_status": "assistant_connector_status",
    "workflow_runs": "assistant_workflow_runs",
    "analytics": "assistant_analytics",
    "search_web": "web_search",
    "generate_document": "assistant_generate_document",
    "run_agent_task": "assistant_run_agent_task",
    "create_workflow": "assistant_create_workflow",
    "execute_workflow": "assistant_execute_workflow",
    "dependency_impact": "assistant_dependency_impact",
}

REGISTRY_TO_ASSISTANT_DISPLAY: dict[str, str] = {
    "assistant_agent_status": "getAgentStatus",
    "assistant_connector_status": "getConnectorStatus",
    "assistant_workflow_runs": "getWorkflowRuns",
    "assistant_analytics": "getAnalytics",
    "assistant_generate_document": "generateDocument",
    "assistant_run_agent_task": "runAgentTask",
    "assistant_create_workflow": "createWorkflow",
    "assistant_execute_workflow": "executeWorkflow",
    "assistant_dependency_impact": "estimateDependencyImpact",
    "web_search": "searchWeb",
}

MODE_CONFIG: dict[str, dict[str, Any]] = {
    "fast": {
        "max_iterations": 3,
        "tool_names": ["knowledge_base", "agent_status", "connector_status"],
    },
    "standard": {
        "max_iterations": 6,
        "tool_names": [
            "knowledge_base",
            "agent_status",
            "connector_status",
            "workflow_runs",
            "execute_workflow",
            "search_web",
        ],
    },
    "reasoning": {
        "max_iterations": 10,
        "tool_names": [
            "knowledge_base",
            "agent_status",
            "connector_status",
            "workflow_runs",
            "execute_workflow",
            "analytics",
            "search_web",
            "generate_document",
            "dependency_impact",
        ],
    },
    "agent": {
        "max_iterations": 15,
        "tool_names": "all",
    },
}


def normalize_mode(mode: str | None) -> str:
    value = (mode or "standard").strip().lower()
    if value == "deep":
        return "agent"
    return value if value in MODE_CONFIG else "standard"


def resolve_effective_intelligence_mode(
    mode: str | None,
    connected_integrations: list[str] | None = None,
    *,
    has_mcp_tools: bool = False,
) -> str:
    """Upgrade standard/reasoning to agent when connectors or MCP tools are live.

    Wave 4 — ``fast`` is honest: it keeps the tiny tool set and low iteration
    budget even when connectors are connected (no silent upgrade to agent).
    """
    normalized = normalize_mode(mode)
    if normalized == "fast":
        return "fast"
    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    connected = [c for c in connected if c not in {"platform", "webhook", "email"}]
    if (connected or has_mcp_tools) and normalized in {"standard", "reasoning"}:
        return "agent"
    return normalized


def normalize_assistant_tool_id(tool_id: str) -> str:
    """Accept legacy `web_search` id from callers; canonical id is `search_web`."""
    value = str(tool_id or "").strip()
    if value == "web_search":
        return "search_web"
    return value


def resolve_assistant_tool_names(mode: str | None, requested: list[str] | None) -> list[str]:
    """Resolve assistant tool ids for a chat request."""
    if requested is not None:
        normalized = [normalize_assistant_tool_id(str(t)) for t in requested]
        return [
            tool_id
            for tool_id in normalized
            if tool_id in ASSISTANT_TOOL_TO_REGISTRY or tool_id in ALL_ASSISTANT_TOOL_NAMES
        ]
    normalized = normalize_mode(mode)
    config = MODE_CONFIG[normalized]
    tool_names = config.get("tool_names")
    if tool_names == "all":
        return list(ALL_ASSISTANT_TOOL_NAMES)
    return list(tool_names or MODE_CONFIG["standard"]["tool_names"])


def resolve_registry_permitted_tools(tool_names: list[str]) -> list[str]:
    """Map assistant tool ids to ToolRegistry tool names (excludes knowledge_base)."""
    permitted: list[str] = []
    for name in tool_names:
        registry_name = ASSISTANT_TOOL_TO_REGISTRY.get(name)
        if registry_name:
            permitted.append(registry_name)
    return permitted


def expand_registry_with_connected_integrations(
    permitted: list[str],
    connected_integrations: list[str],
) -> list[str]:
    """Allow native connector invoke tools in ReAct when integrations are connected."""
    expanded = list(permitted)
    seen = {p.lower() for p in expanded}
    for integration in connected_integrations:
        key = str(integration or "").strip().lower()
        if not key or key == "platform":
            continue
        if key not in seen:
            expanded.append(key)
            seen.add(key)
    return expanded


def mode_includes_tool(mode: str | None, tool_id: str) -> bool:
    return normalize_assistant_tool_id(tool_id) in resolve_assistant_tool_names(mode, None)


def registry_to_assistant_tool_id(registry_name: str) -> str | None:
    for assistant_id, mapped in ASSISTANT_TOOL_TO_REGISTRY.items():
        if mapped == registry_name:
            return assistant_id
    return None
