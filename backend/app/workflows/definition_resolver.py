"""Compile executable workflow definitions for the execute.py façade (STA-271 Phase B)."""
from __future__ import annotations

from typing import Any

from app.workflows.builder_sync import graph_to_definition
from app.workflows.constants import SCHEMA_VERSION
from app.workflows.repository import list_workflow_edges, list_workflow_nodes

_LEGACY_NODE_TYPE_MAP = {
    "trigger": "source",
    "action": "tool",
    "end": "task",
    "human_approval": "approval",
    "loop": "task",
    "parallel": "task",
    "delay": "task",
}


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
    normalized["node_type"] = _LEGACY_NODE_TYPE_MAP.get(raw_type, raw_type)
    if not normalized.get("name") and normalized.get("title"):
        normalized["name"] = normalized["title"]
    return normalized


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
        if isinstance(graph_nodes, list) and graph_nodes and not graph_edges:
            resolved["graph"] = {
                "nodes": graph_nodes,
                "edges": _normalize_edges([], graph_nodes),
            }
        return resolved

    if isinstance(graph_nodes, list) and graph_nodes:
        edges = _normalize_edges(graph_edges or [], graph_nodes)
        resolved["graph"] = {"nodes": graph_nodes, "edges": edges}
        compiled = graph_to_definition(graph_nodes, edges)
        resolved["schema_version"] = compiled.get("schema_version") or SCHEMA_VERSION
        resolved["steps"] = compiled.get("steps") or []
        return resolved

    db_nodes = list_workflow_nodes(client, org_id, workflow_id, environment_name)
    if not db_nodes:
        return resolved

    normalized_nodes = [_normalize_db_node(node) for node in db_nodes]
    db_edges = list_workflow_edges(client, org_id, workflow_id, environment_name)
    edge_dicts = _normalize_edges(db_edges, normalized_nodes)
    compiled = graph_to_definition(normalized_nodes, edge_dicts)
    resolved["schema_version"] = compiled.get("schema_version") or SCHEMA_VERSION
    resolved["steps"] = compiled.get("steps") or []
    resolved["graph"] = {"nodes": normalized_nodes, "edges": edge_dicts}
    return resolved
