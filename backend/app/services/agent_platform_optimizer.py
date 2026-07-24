"""Agent platform performance optimizations — tool visibility, schema compression, routing helpers."""
from __future__ import annotations

import copy
import re
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_PLATFORM_PREFIXES = ("assistant_", "web_search", "browser_", "knowledge_")
_WRITE_TOOL_HINT = re.compile(r"\b(create|update|delete|send|post|write|assign|enroll|close|notify)\b", re.I)
_CONNECTOR_HINT = re.compile(
    r"\b(apollo|hubspot|slack|salesforce|jira|github|notion|stripe|asana|gmail|"
    r"monday|pipedrive|zendesk|linear|quickbooks|xero|plaid|gusto)\b",
    re.I,
)
_TOKEN = re.compile(r"[a-z0-9_]{3,}", re.I)

_MAX_TOOLS_DEFAULT = 28
_MAX_PER_CONNECTOR = 10
_MAX_DESC_CHARS = 140


def _tool_name(tool: dict[str, Any]) -> str:
    fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
    return str(fn.get("name") or tool.get("name") or "")


def _tool_integration(tool: dict[str, Any]) -> str:
    name = _tool_name(tool)
    if name.startswith("assistant_"):
        return "platform"
    if "_" in name:
        return name.split("_", 1)[0].lower()
    return name.lower()


def _is_platform_tool(tool: dict[str, Any]) -> bool:
    name = _tool_name(tool).lower()
    return tool.get("always_available") is True or name.startswith(_PLATFORM_PREFIXES)


def _is_write_tool(tool: dict[str, Any]) -> bool:
    tier = str(tool.get("capability_tier") or "").lower()
    if tier == "write" or tool.get("requires_approval") is True:
        return True
    name = _tool_name(tool).lower()
    return any(token in name for token in ("create", "update", "delete", "send", "post", "write", "assign"))


def _query_tokens(query: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(query or "")}


def _mentioned_connectors(
    query: str,
    classification: dict[str, Any] | None,
    connected: list[str],
) -> set[str]:
    from app.services.chat_connector_models import INTEGRATION_ALIASES

    text = (query or "").lower()
    hits = {c.lower() for c in connected if c.lower() in text}
    for match in _CONNECTOR_HINT.finditer(text):
        hits.add(match.group(1).lower())
    for slug, aliases in INTEGRATION_ALIASES.items():
        if slug in hits:
            continue
        for alias in aliases:
            alias_norm = alias.strip().lower()
            if alias_norm and re.search(rf"\b{re.escape(alias_norm)}\b", text, re.I):
                hits.add(slug)
                break
    cls = classification or {}
    for key in ("integration", "connector", "preferred_connector", "channel_override"):
        value = str(cls.get(key) or "").strip().lower()
        if value:
            hits.add(value)
    systems = cls.get("systems") or cls.get("connected_integrations") or []
    if isinstance(systems, list):
        hits.update(str(s).strip().lower() for s in systems if str(s).strip())
    return hits


def _ensure_connected_tool_coverage(
    selected: list[dict[str, Any]],
    connector_tools: list[dict[str, Any]],
    connected: list[str],
    *,
    focus: set[str],
    max_tools: int,
    platform_count: int,
    action_required: bool,
) -> list[dict[str, Any]]:
    """Keep at least one tool per connected vendor in the visible set (gap 1)."""
    skip = {"platform", "mcp", "browser", "webhook", "email"}
    selected_ids = {id(tool) for tool in selected}
    budget = max(1, max_tools - platform_count)

    for integration in connected:
        key = str(integration or "").strip().lower()
        if not key or key in skip:
            continue
        if any(_tool_integration(tool) == key for tool in selected):
            continue
        pool = [tool for tool in connector_tools if _tool_integration(tool) == key]
        if not pool:
            continue
        if not action_required:
            read_pool = [tool for tool in pool if not _is_write_tool(tool)]
            pool = read_pool or pool
        pool.sort(key=lambda tool: _score_tool(tool, set(), focus, query), reverse=True)
        pick = pool[0]
        if id(pick) in selected_ids:
            continue
        if len(selected) >= budget:
            # Drop lowest-scored non-focus tool to make room for connected coverage.
            droppable = [
                (idx, tool)
                for idx, tool in enumerate(selected)
                if _tool_integration(tool) not in focus and _tool_integration(tool) not in connected
            ]
            if not droppable:
                continue
            drop_idx = min(droppable, key=lambda row: _score_tool(row[1], set(), focus, query))[0]
            removed = selected.pop(drop_idx)
            selected_ids.discard(id(removed))
        selected.append(pick)
        selected_ids.add(id(pick))
    return selected


def _score_tool(tool: dict[str, Any], tokens: set[str], focus: set[str], query: str = "") -> float:
    name = _tool_name(tool).lower()
    desc = str((tool.get("function") or {}).get("description") or tool.get("description") or "").lower()
    integration = _tool_integration(tool)
    score = 0.0
    if integration in focus:
        score += 2.0
    overlap = tokens & set(name.replace("_", " ").split())
    score += 0.35 * len(overlap)
    if any(token in name or token in desc for token in tokens):
        score += 0.2
    if _is_write_tool(tool):
        score += 0.05
    return score


def compress_tool_parameters(params: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(params, dict):
        return {"type": "object", "properties": {}}
    slim = {"type": params.get("type") or "object"}
    props = params.get("properties")
    if isinstance(props, dict):
        slim_props: dict[str, Any] = {}
        for key, spec in props.items():
            if isinstance(spec, dict):
                slim_props[key] = {"type": spec.get("type") or "string"}
            else:
                slim_props[key] = spec
        slim["properties"] = slim_props
    required = params.get("required")
    if isinstance(required, list) and required:
        slim["required"] = required
    return slim


def compress_tool_definition(tool: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(tool)
    fn = out.get("function")
    if not isinstance(fn, dict):
        return out
    desc = str(fn.get("description") or "").strip()
    if len(desc) > _MAX_DESC_CHARS:
        fn["description"] = desc[: _MAX_DESC_CHARS - 1].rstrip() + "…"
    fn["parameters"] = compress_tool_parameters(fn.get("parameters") or {})
    return out


def compress_tool_definitions(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [compress_tool_definition(tool) for tool in tools]


def narrow_tools_for_turn(
    tools: list[dict[str, Any]],
    *,
    query: str,
    classification: dict[str, Any] | None = None,
    connector_names: tuple[str, ...] | list[str] | None = None,
    connected_integrations: list[str] | None = None,
    requires_action: bool | None = None,
    max_tools: int = _MAX_TOOLS_DEFAULT,
    max_per_connector: int = _MAX_PER_CONNECTOR,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return a focused tool subset plus compression stats for observability."""
    if not tools:
        return [], {"totalTools": 0, "visibleTools": 0}

    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    platform_tools = [t for t in tools if _is_platform_tool(t)]
    connector_tools = [t for t in tools if not _is_platform_tool(t)]

    focus = {str(c).strip().lower() for c in (connector_names or []) if str(c).strip()}
    focus |= _mentioned_connectors(query, classification, connected)
    if not focus and connected:
        focus = set(connected[:3])

    action_required = (
        bool(requires_action)
        if requires_action is not None
        else bool((classification or {}).get("requires_action"))
        or bool(_WRITE_TOOL_HINT.search(query or ""))
    )

    tokens = _query_tokens(query)
    scored: list[tuple[float, dict[str, Any]]] = []
    for tool in connector_tools:
        integration = _tool_integration(tool)
        if focus and integration not in focus and integration not in {"platform", "mcp", "browser"}:
            continue
        if not action_required and _is_write_tool(tool):
            continue
        scored.append((_score_tool(tool, tokens, focus, query), tool))

    scored.sort(key=lambda row: row[0], reverse=True)
    selected_connector: list[dict[str, Any]] = []
    per_connector: dict[str, int] = {}
    for _, tool in scored:
        integration = _tool_integration(tool)
        if per_connector.get(integration, 0) >= max_per_connector:
            continue
        selected_connector.append(tool)
        per_connector[integration] = per_connector.get(integration, 0) + 1
        if len(selected_connector) >= max(1, max_tools - len(platform_tools)):
            break

    if action_required:
        for tool in connector_tools:
            if not _is_write_tool(tool):
                continue
            integration = _tool_integration(tool)
            if focus and integration not in focus:
                continue
            if tool in selected_connector:
                continue
            selected_connector.append(tool)

    if len(selected_connector) < 3 and len(connector_tools) > max_tools:
        rescored = sorted(
            ((_score_tool(t, tokens, focus, query), t) for t in connector_tools),
            key=lambda row: row[0],
            reverse=True,
        )
        selected_connector = [t for _, t in rescored[: max_tools - len(platform_tools)]]

    selected_connector = _ensure_connected_tool_coverage(
        selected_connector,
        connector_tools,
        connected,
        focus=focus,
        max_tools=max_tools,
        platform_count=len(platform_tools),
        action_required=action_required,
    )

    visible = platform_tools + selected_connector
    compressed = compress_tool_definitions(visible)
    stats = {
        "totalTools": len(tools),
        "visibleTools": len(compressed),
        "focusedConnectors": sorted(focus),
        "actionRequired": action_required,
        "compressed": True,
    }
    return compressed, stats


def build_progress_steps(
    *,
    routing_tier: str,
    connected_integrations: list[str] | None = None,
    connector_names: tuple[str, ...] | list[str] | None = None,
    phase: str = "context",
) -> list[str]:
    names = [str(c) for c in (connector_names or []) if str(c).strip()]
    if not names:
        names = [str(c) for c in (connected_integrations or [])[:4] if str(c).strip()]
    label = ", ".join(n.capitalize() for n in names[:4]) if names else "connected systems"
    if phase == "context":
        return [
            f"Routing tier: {routing_tier.replace('_', ' ')}",
            f"Reviewing {label}",
            "Loading memory and knowledge",
        ]
    if phase == "tools":
        return [f"Preparing tools for {label}"]
    return [f"Running {routing_tier.replace('_', ' ')} analysis"]
