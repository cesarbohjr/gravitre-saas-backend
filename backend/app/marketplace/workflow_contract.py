"""Rich workflow contract nodes for marketplace / intelligence-pack installs.

Pack installs historically wrote thin ``{id, type, name}`` stubs into
``workflows.nodes``, which the builder preferred over the rich
``workflow_defs.definition`` — leaving agents unbound and instructions empty.
"""
from __future__ import annotations

from typing import Any


def resolve_step_agent_seeds(
    steps: list[dict[str, Any]],
    *,
    agent_ids_by_seed: dict[str, str],
) -> list[dict[str, Any]]:
    """Map ``metadata.agent_seed`` / ``next_agent_seed`` → concrete agent UUIDs."""
    resolved: list[dict[str, Any]] = []
    for step in steps:
        row = dict(step)
        metadata = dict(row.get("metadata") or {})
        seed = metadata.pop("agent_seed", None)
        if seed:
            agent_id = agent_ids_by_seed.get(str(seed))
            if agent_id:
                metadata["agent_id"] = agent_id
            else:
                # Keep seed so builder load can still bind later.
                metadata["agent_seed"] = seed
        next_seed = metadata.pop("next_agent_seed", None)
        if next_seed:
            next_id = agent_ids_by_seed.get(str(next_seed))
            if next_id:
                metadata["next_agent_id"] = next_id
            else:
                metadata["next_agent_seed"] = next_seed
        if metadata:
            row["metadata"] = metadata
        resolved.append(row)
    return resolved


def steps_to_rich_contract(
    steps: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build builder-ready ``workflows.nodes`` / ``edges`` from definition steps."""
    from app.workflows.builder_sync import definition_to_builder_nodes

    builder_nodes, builder_edges = definition_to_builder_nodes(
        {"steps": steps},
    )
    nodes: list[dict[str, Any]] = []
    for node in builder_nodes:
        nodes.append(
            {
                "id": node.get("id"),
                "type": node.get("node_type") or node.get("type") or "task",
                "node_type": node.get("node_type") or node.get("type") or "task",
                "name": node.get("name") or node.get("title"),
                "title": node.get("title") or node.get("name"),
                "description": node.get("description"),
                "config": node.get("config") or {},
                "metadata": node.get("metadata") or {},
                "position": node.get("position")
                or {
                    "x": node.get("position_x") or 0,
                    "y": node.get("position_y") or 0,
                },
            }
        )
    edges = [
        {
            "from": edge.get("from_node_id") or edge.get("from"),
            "to": edge.get("to_node_id") or edge.get("to"),
        }
        for edge in builder_edges
        if (edge.get("from_node_id") or edge.get("from"))
        and (edge.get("to_node_id") or edge.get("to"))
    ]
    return nodes, edges
