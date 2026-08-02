"""Compile executable workflow definitions for the execute.py façade (STA-271 Phase B)."""
from __future__ import annotations

from typing import Any

from app.workflows.builder_sync import graph_to_definition
from app.workflows.constants import SCHEMA_VERSION
from app.workflows.repository import list_workflow_edges, list_workflow_nodes

# Shared with builder_sync — single map so human_approval cannot degrade to task.
LEGACY_NODE_TYPE_MAP = {
    "trigger": "source",
    "action": "tool",
    "end": "task",
    "human_approval": "approval",
    # Keep loop/if/switch/merge as first-class canvas types (builder_sync compiles them).
    "parallel": "task",
    "delay": "task",
}

# Backward-compatible alias for existing imports/tests.
_LEGACY_NODE_TYPE_MAP = LEGACY_NODE_TYPE_MAP


def normalize_legacy_node_type(raw_type: str | None) -> str:
    """Map legacy/canvas aliases onto executable node types (human_approval → approval)."""
    text = str(raw_type or "task").strip().lower()
    return LEGACY_NODE_TYPE_MAP.get(text, text) or "task"


def _sequential_edges(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        nodes,
        key=lambda node: (int(node.get("order_index") or 0), str(node.get("id") or "")),
    )
    edges: list[dict[str, Any]] = []
    for index in range(len(ordered) - 1):
        edges.append(
            {
                "from_node_id": str(ordered[index]["id"]),
                "to_node_id": str(ordered[index + 1]["id"]),
            }
        )
    return edges


def _normalize_db_node(node: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(node)
    raw_type = str(normalized.get("node_type") or normalized.get("type") or "task").strip()
    mapped = normalize_legacy_node_type(raw_type)
    normalized["node_type"] = mapped
    if mapped == "approval":
        metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
        normalized["metadata"] = {**metadata, "has_approval_gate": True}
    if not normalized.get("name") and normalized.get("title"):
        normalized["name"] = normalized["title"]
    return normalized


def _normalize_step_types(steps: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        normalized = dict(step)
        mapped = normalize_legacy_node_type(str(normalized.get("type") or "noop"))
        normalized["type"] = mapped
        if mapped == "approval":
            metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
            normalized["metadata"] = {**metadata, "has_approval_gate": True}
        out.append(normalized)
    return out


def _normalize_graph_types(graph_block: dict[str, Any]) -> dict[str, Any]:
    nodes = graph_block.get("nodes") if isinstance(graph_block.get("nodes"), list) else []
    edges = graph_block.get("edges") if isinstance(graph_block.get("edges"), list) else []
    normalized_nodes = [_normalize_db_node(node) if isinstance(node, dict) else node for node in nodes]
    return {"nodes": normalized_nodes, "edges": edges}


def _normalize_edges(edges: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if edges:
        normalized: list[dict[str, Any]] = []
        for edge in edges:
            from_id = str(edge.get("from_node_id") or edge.get("from") or "")
            to_id = str(edge.get("to_node_id") or edge.get("to") or "")
            if from_id and to_id:
                normalized.append({"from_node_id": from_id, "to_node_id": to_id})
        if normalized:
            return normalized
    return _sequential_edges(nodes)


_ENRICHMENT_CHAIN_ACTIONS = frozenset(
    {
        "clay.leads.push",
        "clay.workflows.output.get",
        "clay.crm.sync",
        "apollo.contacts.search",
        "apollo.people.search",
    }
)


def _step_actions(steps: list[Any]) -> set[str]:
    actions: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            continue
        config = step.get("config") if isinstance(step.get("config"), dict) else {}
        action = str(config.get("action") or config.get("tool_action") or "").strip()
        if action:
            actions.add(action)
    return actions


def _is_enrichment_chain(steps: list[Any], nodes: list[Any]) -> bool:
    actions = _step_actions(steps)
    if actions & {"clay.crm.sync", "clay.leads.push"}:
        return True
    for node in nodes:
        if not isinstance(node, dict):
            continue
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        action = str(config.get("action") or config.get("tool_action") or "").strip()
        if action in _ENRICHMENT_CHAIN_ACTIONS:
            return True
        blob = f"{node.get('name') or ''} {node.get('title') or ''}".lower()
        if "clay" in blob and ("hubspot" in blob or "enrich" in blob or "sync" in blob):
            return True
    return False


def _sequential_edges_from_step_order(
    steps: list[Any],
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    node_ids = {str(node.get("id")) for node in nodes if isinstance(node, dict) and node.get("id")}
    ordered = [
        str(step["id"])
        for step in steps
        if isinstance(step, dict) and step.get("id") and str(step["id"]) in node_ids
    ]
    if len(ordered) < 2:
        return None
    return [
        {"from_node_id": ordered[index], "to_node_id": ordered[index + 1]}
        for index in range(len(ordered) - 1)
    ]


def _repair_enrichment_graph_edges(
    resolved: dict[str, Any],
) -> dict[str, Any]:
    """Force a single serial chain when Clay→HubSpot graphs have orphan roots.

    Disconnected ``clay.crm.sync`` nodes otherwise run in the first parallel batch
    with empty ``upstream_outputs`` and fail on missing records.
    """
    steps = resolved.get("steps") if isinstance(resolved.get("steps"), list) else []
    graph = resolved.get("graph") if isinstance(resolved.get("graph"), dict) else {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    if not steps or not nodes:
        return resolved
    if not _is_enrichment_chain(steps, nodes):
        return resolved
    normalized_edges = _normalize_edges(edges, [n for n in nodes if isinstance(n, dict)])
    targets = {edge["to_node_id"] for edge in normalized_edges}
    roots = [
        str(node.get("id"))
        for node in nodes
        if isinstance(node, dict) and node.get("id") and str(node.get("id")) not in targets
    ]
    if len(roots) <= 1:
        resolved["graph"] = {**graph, "edges": normalized_edges}
        return resolved
    repaired = _sequential_edges_from_step_order(steps, [n for n in nodes if isinstance(n, dict)])
    if not repaired:
        repaired = _sequential_edges([n for n in nodes if isinstance(n, dict)])
    resolved["graph"] = {**graph, "edges": repaired}
    return resolved


def resolve_executable_definition(
    client: Any,
    org_id: str,
    workflow_id: str,
    definition: dict[str, Any] | None,
    environment_name: str = "default",
) -> dict[str, Any]:
    """Ensure definition has a graph (preferred) or steps for ``execute_workflow_steps``."""
    resolved = dict(definition or {})
    graph_block = resolved.get("graph") if isinstance(resolved.get("graph"), dict) else {}
    graph_nodes = graph_block.get("nodes") if isinstance(graph_block.get("nodes"), list) else None
    graph_edges = graph_block.get("edges") if isinstance(graph_block.get("edges"), list) else None
    steps = resolved.get("steps")

    if isinstance(steps, list) and steps:
        resolved["steps"] = _normalize_step_types(steps)
        if isinstance(graph_nodes, list) and graph_nodes:
            normalized_graph = _normalize_graph_types(
                {"nodes": graph_nodes, "edges": graph_edges or []}
            )
            if not graph_edges:
                normalized_graph["edges"] = _normalize_edges([], normalized_graph["nodes"])
            resolved["graph"] = normalized_graph
            return _repair_enrichment_graph_edges(resolved)
        return resolved

    if isinstance(graph_nodes, list) and graph_nodes:
        normalized_graph = _normalize_graph_types(
            {"nodes": graph_nodes, "edges": graph_edges or []}
        )
        edges = _normalize_edges(normalized_graph.get("edges") or [], normalized_graph["nodes"])
        resolved["graph"] = {"nodes": normalized_graph["nodes"], "edges": edges}
        compiled = graph_to_definition(normalized_graph["nodes"], edges)
        resolved["schema_version"] = compiled.get("schema_version") or SCHEMA_VERSION
        resolved["steps"] = _normalize_step_types(compiled.get("steps") or [])
        return _repair_enrichment_graph_edges(resolved)

    db_nodes = list_workflow_nodes(client, org_id, workflow_id, environment_name)
    if not db_nodes:
        if isinstance(steps, list) and steps:
            resolved["steps"] = _normalize_step_types(steps)
        return resolved

    normalized_nodes = [_normalize_db_node(node) for node in db_nodes]
    db_edges = list_workflow_edges(client, org_id, workflow_id, environment_name)
    edge_dicts = _normalize_edges(db_edges, normalized_nodes)
    compiled = graph_to_definition(normalized_nodes, edge_dicts)
    resolved["schema_version"] = compiled.get("schema_version") or SCHEMA_VERSION
    resolved["steps"] = _normalize_step_types(compiled.get("steps") or [])
    resolved["graph"] = {"nodes": normalized_nodes, "edges": edge_dicts}
    return _repair_enrichment_graph_edges(resolved)
