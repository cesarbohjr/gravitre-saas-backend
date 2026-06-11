"""STA-19: Persist visual builder graph and compile to workflow_defs steps."""
from __future__ import annotations

import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from app.workflows.constants import SCHEMA_VERSION
from app.workflows.repository import (
    create_workflow_edge,
    create_workflow_node,
    create_workflow_version,
    get_next_workflow_version_number,
    set_active_workflow_version,
)
from app.workflows.schema import validate_definition


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def _node_position(node: dict[str, Any]) -> dict[str, int]:
    position = node.get("position")
    if isinstance(position, dict):
        return {"x": int(position.get("x") or 0), "y": int(position.get("y") or 0)}
    return {
        "x": int(node.get("position_x") or 0),
        "y": int(node.get("position_y") or 0),
    }


def _outgoing_targets(node_id: str, edges: list[dict[str, Any]]) -> list[str]:
    return [str(e["to_node_id"]) for e in edges if str(e.get("from_node_id")) == str(node_id)]


def _topological_node_order(node_ids: list[str], edges: list[dict[str, Any]]) -> list[str]:
    indegree: dict[str, int] = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        src = str(edge.get("from_node_id") or "")
        dst = str(edge.get("to_node_id") or "")
        if src not in indegree or dst not in indegree:
            continue
        adjacency[src].append(dst)
        indegree[dst] += 1
    queue = deque([nid for nid in node_ids if indegree[nid] == 0])
    ordered: list[str] = []
    while queue:
        current = queue.popleft()
        ordered.append(current)
        for nxt in adjacency.get(current, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    for nid in node_ids:
        if nid not in ordered:
            ordered.append(nid)
    return ordered


def _resolve_agent_ids(node: dict[str, Any], nodes_by_id: dict[str, dict], edges: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
    agent_id = (
        metadata.get("agent_id")
        or metadata.get("agentId")
        or config.get("agent_id")
        or config.get("agentId")
        or node.get("operator_id")
    )
    next_agent_id = metadata.get("next_agent_id") or metadata.get("nextAgentId") or config.get("next_agent_id")
    if not next_agent_id:
        for target_id in _outgoing_targets(str(node["id"]), edges):
            target = nodes_by_id.get(target_id)
            if not target or (target.get("node_type") or "") != "agent":
                continue
            t_cfg = target.get("config") if isinstance(target.get("config"), dict) else {}
            t_meta = target.get("metadata") if isinstance(target.get("metadata"), dict) else {}
            candidate = (
                t_meta.get("agent_id")
                or t_meta.get("agentId")
                or t_cfg.get("agent_id")
                or t_cfg.get("agentId")
                or target.get("operator_id")
            )
            if candidate:
                next_agent_id = str(candidate)
                break
    return (str(agent_id) if agent_id else None, str(next_agent_id) if next_agent_id else None)


def _node_to_step(node: dict[str, Any], nodes_by_id: dict[str, dict], edges: list[dict[str, Any]]) -> dict[str, Any] | None:
    node_type = str(node.get("node_type") or node.get("type") or "").strip()
    step_id = str(node["id"])
    name = str(node.get("name") or node.get("title") or step_id)
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}

    if node_type in {"source", "trigger"}:
        return None
    if node_type == "agent":
        agent_id, next_agent_id = _resolve_agent_ids(node, nodes_by_id, edges)
        step_metadata: dict[str, Any] = {
            "task": metadata.get("task") or config.get("task") or node.get("instruction") or name,
        }
        if agent_id:
            step_metadata["agent_id"] = agent_id
        if next_agent_id:
            step_metadata["next_agent_id"] = next_agent_id
            step_metadata["receiver_task"] = (
                metadata.get("receiver_task")
                or config.get("receiver_task")
                or "Continue workflow using the handoff briefing"
            )
        if metadata.get("role"):
            step_metadata["role"] = metadata.get("role")
        return {"id": step_id, "name": name, "type": "agent", "metadata": step_metadata, "config": {}}
    if node_type == "connector":
        tool_action = config.get("tool_action") or config.get("action")
        if tool_action in {"slack.post_message", "slack_post_message"}:
            return {
                "id": step_id,
                "name": name,
                "type": "slack_post_message",
                "config": {k: v for k, v in config.items() if k != "tool_action"},
            }
        if tool_action in {"email.send", "email_send"}:
            return {"id": step_id, "name": name, "type": "email_send", "config": dict(config)}
        if tool_action in {"webhook.post", "webhook_post"}:
            return {"id": step_id, "name": name, "type": "webhook_post", "config": dict(config)}
    if node_type == "tool":
        mapped = config.get("step_type") or config.get("tool_action")
        if mapped in {"slack_post_message", "email_send", "webhook_post", "rag_retrieve", "noop"}:
            return {"id": step_id, "name": name, "type": str(mapped), "config": dict(config)}
    if node_type == "council":
        council_cfg = metadata.get("councilConfig") if isinstance(metadata.get("councilConfig"), dict) else {}
        if not council_cfg and isinstance(config.get("councilConfig"), dict):
            council_cfg = config.get("councilConfig")
        return {
            "id": step_id,
            "name": name,
            "type": "council",
            "config": {
                "objective": council_cfg.get("objective") or metadata.get("objective"),
                "options": council_cfg.get("options") or ["enroll", "nurture"],
                "output_paths": council_cfg.get("outputPaths") or council_cfg.get("output_paths") or {},
                "decision_method": council_cfg.get("decisionMethod") or council_cfg.get("decision_method"),
                "confidence_threshold": council_cfg.get("confidenceThreshold")
                or council_cfg.get("confidence_threshold"),
                "source_step_id": council_cfg.get("sourceStepId") or council_cfg.get("source_step_id"),
                "agent_ids": council_cfg.get("agentIds") or council_cfg.get("agent_ids") or [],
                "max_rounds": council_cfg.get("maxRounds") or council_cfg.get("max_rounds"),
            },
            "metadata": metadata or {},
        }
    if node_type in {"approval", "decision", "task"}:
        return {
            "id": step_id,
            "name": name,
            "type": "noop",
            "config": {"builder_node_type": node_type},
            "metadata": metadata or {"simulated": True},
        }
    return {"id": step_id, "name": name, "type": "noop", "config": dict(config)}


def definition_to_builder_nodes(definition: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Hydrate a minimal canvas from stored step definitions when graph rows are absent."""
    steps = definition.get("steps") if isinstance(definition.get("steps"), list) else []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    x = 120
    prev_id: str | None = None
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("id") or f"step-{idx + 1}")
        step_type = str(step.get("type") or "noop")
        metadata = step.get("metadata") if isinstance(step.get("metadata"), dict) else {}
        config = step.get("config") if isinstance(step.get("config"), dict) else {}
        node_type = "agent" if step_type == "agent" else "tool" if step_type in {"slack_post_message", "email_send", "webhook_post"} else "task"
        nodes.append(
            {
                "id": step_id,
                "node_type": node_type,
                "title": str(step.get("name") or step_id),
                "name": str(step.get("name") or step_id),
                "config": config,
                "metadata": metadata,
                "position": {"x": x, "y": 160},
                "position_x": x,
                "position_y": 160,
            }
        )
        if prev_id:
            edges.append({"from_node_id": prev_id, "to_node_id": step_id})
        prev_id = step_id
        x += 260
    return nodes, edges


def graph_to_definition(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    nodes_by_id = {str(n["id"]): n for n in nodes}
    order = _topological_node_order(list(nodes_by_id.keys()), edges)
    steps: list[dict[str, Any]] = []
    for node_id in order:
        step = _node_to_step(nodes_by_id[node_id], nodes_by_id, edges)
        if step:
            steps.append(step)
    return {"schema_version": SCHEMA_VERSION, "steps": steps}


def delete_workflow_graph(
    client: Any,
    org_id: str,
    workflow_id: str,
    environment_name: str,
) -> None:
    client.table("workflow_connections").delete().eq("org_id", org_id).eq("workflow_id", workflow_id).eq(
        "environment", environment_name
    ).execute()
    client.table("workflow_nodes").delete().eq("org_id", org_id).eq("workflow_id", workflow_id).eq(
        "environment", environment_name
    ).execute()


def sync_builder_graph(
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    created_by: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Replace workflow graph, compile definition, publish active version."""
    delete_workflow_graph(client, org_id, workflow_id, environment_name)

    id_map: dict[str, str] = {}
    stored_nodes: list[dict[str, Any]] = []
    for raw in nodes:
        client_id = str(raw.get("id") or "")
        if not client_id:
            continue
        position = _node_position(raw)
        node_type = str(raw.get("type") or raw.get("node_type") or "task")
        config = raw.get("config") if isinstance(raw.get("config"), dict) else {}
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        if not metadata:
            for key in ("decisionConfig", "councilConfig", "outputPaths"):
                if key in raw:
                    metadata[key] = raw[key]
        payload = {
            "node_type": node_type,
            "title": str(raw.get("name") or raw.get("title") or "Node"),
            "name": raw.get("name"),
            "description": raw.get("description"),
            "instruction": raw.get("description"),
            "config": config,
            "metadata": metadata,
            "position": position,
            "position_x": position["x"],
            "position_y": position["y"],
            "operator_id": raw.get("operator_id") or config.get("agent_id") or config.get("agentId"),
            "connector_id": raw.get("connector_id") or config.get("connector_id"),
            "source_id": raw.get("source_id"),
            "has_approval_gate": node_type == "approval",
        }
        if _is_uuid(client_id):
            payload["id"] = client_id
        created = create_workflow_node(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            environment_name=environment_name,
            payload=payload,
            created_by=created_by,
        )
        id_map[client_id] = str(created["id"])
        stored_nodes.append(created)

    stored_edges: list[dict[str, Any]] = []
    for raw in edges:
        from_id = id_map.get(str(raw.get("from_node_id") or raw.get("from") or ""))
        to_id = id_map.get(str(raw.get("to_node_id") or raw.get("to") or ""))
        if not from_id or not to_id:
            continue
        edge = create_workflow_edge(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            environment_name=environment_name,
            payload={
                "from_node_id": from_id,
                "to_node_id": to_id,
                "edge_type": raw.get("edge_type"),
                "condition": raw.get("condition"),
            },
            created_by=created_by,
        )
        stored_edges.append(edge)

    definition = validate_definition(graph_to_definition(stored_nodes, stored_edges))
    definition["graph"] = {
        "nodes": stored_nodes,
        "edges": [
            {
                "from_node_id": str(edge["from_node_id"]),
                "to_node_id": str(edge["to_node_id"]),
            }
            for edge in stored_edges
        ],
    }
    client.table("workflow_defs").update(
        {
            "definition": definition,
            "schema_version": definition.get("schema_version") or SCHEMA_VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", workflow_id).eq("org_id", org_id).execute()

    version_number = get_next_workflow_version_number(client, org_id, workflow_id, environment_name)
    version_row = create_workflow_version(
        client,
        org_id=org_id,
        workflow_id=workflow_id,
        environment_name=environment_name,
        version=version_number,
        definition=definition,
        schema_version=definition.get("schema_version") or SCHEMA_VERSION,
        created_by=created_by,
    )
    set_active_workflow_version(
        client,
        org_id=org_id,
        workflow_id=workflow_id,
        environment_name=environment_name,
        version_id=str(version_row["id"]),
        updated_by=created_by,
    )
    return stored_nodes, stored_edges, definition
