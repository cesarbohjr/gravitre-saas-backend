"""STA-135 / AI-005: Graph-native workflow execution engine.

Executes builder graphs (nodes + edges) in topological batches so each node
receives full upstream outputs before it runs. Integrates with the same run/step
logging primitives as ``execute.py``.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.workflows.builder_sync import _node_to_step

_PASSTHROUGH_NODE_TYPES = frozenset({"source", "trigger"})
_APPROVAL_NODE_TYPES = frozenset({"approval"})
_CHECKPOINT_KEY = "_graph_execution"


class GraphValidationError(ValueError):
    """Raised when a workflow graph cannot be executed."""


@dataclass
class ExecutionGraph:
    node_ids: list[str]
    nodes_by_id: dict[str, dict[str, Any]]
    edges: list[tuple[str, str]]
    predecessors: dict[str, list[str]] = field(default_factory=dict)
    successors: dict[str, list[str]] = field(default_factory=dict)
    entry_nodes: list[str] = field(default_factory=list)


def build_execution_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> ExecutionGraph:
    nodes_by_id = {str(n["id"]): n for n in nodes if n.get("id")}
    node_ids = list(nodes_by_id.keys())
    parsed_edges: list[tuple[str, str]] = []
    predecessors: dict[str, list[str]] = {nid: [] for nid in node_ids}
    successors: dict[str, list[str]] = {nid: [] for nid in node_ids}

    for raw in edges:
        src = str(raw.get("from_node_id") or raw.get("from") or "")
        dst = str(raw.get("to_node_id") or raw.get("to") or "")
        if src not in nodes_by_id or dst not in nodes_by_id:
            continue
        parsed_edges.append((src, dst))
        predecessors[dst].append(src)
        successors[src].append(dst)

    entry_nodes = [nid for nid in node_ids if not predecessors[nid]]
    return ExecutionGraph(
        node_ids=node_ids,
        nodes_by_id=nodes_by_id,
        edges=parsed_edges,
        predecessors=predecessors,
        successors=successors,
        entry_nodes=entry_nodes,
    )


def validate_execution_graph(graph: ExecutionGraph) -> None:
    if not graph.node_ids:
        raise GraphValidationError("Graph has no nodes")

    indegree = {nid: len(graph.predecessors.get(nid, [])) for nid in graph.node_ids}
    queue = deque([nid for nid, deg in indegree.items() if deg == 0])
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for nxt in graph.successors.get(current, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited != len(graph.node_ids):
        raise GraphValidationError("Graph contains a cycle")

    if not graph.entry_nodes:
        raise GraphValidationError("Graph has no entry nodes")

    workflow_entries = [
        nid
        for nid, node in graph.nodes_by_id.items()
        if str(node.get("node_type") or node.get("type") or "") in _PASSTHROUGH_NODE_TYPES
    ]
    if not workflow_entries:
        workflow_entries = list(graph.entry_nodes)

    reachable: set[str] = set()
    stack = list(workflow_entries)
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(graph.successors.get(current, []))

    for node_id, node in graph.nodes_by_id.items():
        node_type = str(node.get("node_type") or node.get("type") or "")
        if node_type in _PASSTHROUGH_NODE_TYPES:
            continue
        step = _node_to_step(node, graph.nodes_by_id, _edges_as_dicts(graph.edges))
        if step is None:
            continue
        if node_id not in reachable:
            raise GraphValidationError(f"Node not reachable from entry points: {node_id}")


def topological_batches(graph: ExecutionGraph) -> list[list[str]]:
    """Return execution batches — all nodes in batch N depend only on batches < N."""
    validate_execution_graph(graph)
    indegree = {nid: len(graph.predecessors.get(nid, [])) for nid in graph.node_ids}
    ready = [nid for nid in graph.node_ids if indegree[nid] == 0]
    batches: list[list[str]] = []
    while ready:
        batch = sorted(ready)
        batches.append(batch)
        next_ready: list[str] = []
        for current in batch:
            for nxt in graph.successors.get(current, []):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    next_ready.append(nxt)
        ready = next_ready
    return batches


def _edges_as_dicts(edges: list[tuple[str, str]]) -> list[dict[str, Any]]:
    return [{"from_node_id": src, "to_node_id": dst} for src, dst in edges]


def _upstream_outputs(graph: ExecutionGraph, node_id: str, node_outputs: dict[str, Any]) -> dict[str, Any]:
    return {
        pred_id: node_outputs[pred_id]
        for pred_id in graph.predecessors.get(node_id, [])
        if pred_id in node_outputs
    }


from app.workflows.execution_engine_runtime import (  # noqa: E402
    execute_workflow_graph,
    resume_paused_workflow_graph,
    resume_workflow_graph,
    retry_workflow_step,
)
