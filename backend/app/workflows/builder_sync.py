"""STA-19: Persist visual builder graph and compile to workflow_defs steps."""
from __future__ import annotations

import logging
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
from app.workflows.schema_sync import (
    _builder_nodes_from_contract,
    contract_edges_from_builder,
    contract_nodes_from_builder,
    sync_legacy_workflow_to_contract,
)

logger = logging.getLogger(__name__)

PERSISTED_GRAPH_NODE_TYPES = frozenset(
    {
        "agent",
        "task",
        "connector",
        "tool",
        "source",
        "approval",
        "council",
        "decision",
        "if",
        "switch",
        "merge",
        "loop",
    }
)
# Canvas-only types stored as task + builder_node_type until DB enum expands.
BUILDER_ONLY_NODE_TYPES = frozenset({"council", "decision", "if", "switch", "merge", "loop"})
LEGACY_PERSISTED_NODE_TYPES = frozenset({"agent", "task", "connector", "tool", "source", "approval"})


def persist_node_type(canvas_type: str) -> tuple[str, dict[str, Any]]:
    """Map builder-only node types to DB-safe types while preserving canvas type in metadata."""
    from app.workflows.definition_resolver import normalize_legacy_node_type

    normalized = normalize_legacy_node_type(canvas_type)
    if normalized in BUILDER_ONLY_NODE_TYPES:
        return "task", {"builder_node_type": normalized}
    if normalized in LEGACY_PERSISTED_NODE_TYPES:
        return normalized, {}
    return "task", {}


def restore_node_type(node: dict[str, Any]) -> str:
    from app.workflows.definition_resolver import normalize_legacy_node_type

    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
    builder_type = metadata.get("builder_node_type")
    if isinstance(builder_type, str) and builder_type in PERSISTED_GRAPH_NODE_TYPES:
        return builder_type
    stored = normalize_legacy_node_type(
        str(node.get("node_type") or node.get("type") or "task")
    )
    if stored in PERSISTED_GRAPH_NODE_TYPES:
        return stored
    return "task"


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


def _normalize_tool_action(config: dict[str, Any]) -> str | None:
    action = config.get("tool_action") or config.get("action")
    if action is None:
        return None
    text = str(action).strip()
    return text or None


def _invoke_tool_step(
    step_id: str,
    name: str,
    config: dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = {k: v for k, v in config.items() if k not in {"tool_action", "action"}}
    action = _normalize_tool_action(config)
    if action:
        cfg["action"] = action
    step: dict[str, Any] = {"id": step_id, "name": name, "type": "invoke_tool", "config": cfg}
    if metadata:
        step["metadata"] = metadata
    return step


def _node_to_step(node: dict[str, Any], nodes_by_id: dict[str, dict], edges: list[dict[str, Any]]) -> dict[str, Any] | None:
    node_type = restore_node_type(node)
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
        if not tool_action:
            vendor = (
                config.get("vendor")
                or config.get("connector")
                or metadata.get("vendor")
            )
            selected = (
                config.get("selected_action")
                or config.get("selectedAction")
                or metadata.get("selectedAction")
            )
            if vendor and selected:
                selected_text = str(selected).strip()
                vendor_text = str(vendor).strip()
                tool_action = (
                    selected_text
                    if selected_text.startswith(f"{vendor_text}.")
                    else f"{vendor_text}.{selected_text}"
                )
                config = {**config, "action": tool_action, "tool_action": tool_action}
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
        if tool_action:
            return _invoke_tool_step(step_id, name, config, metadata=metadata or None)
    if node_type == "tool":
        mapped = config.get("step_type") or config.get("tool_action")
        if mapped in {"slack_post_message", "email_send", "webhook_post", "rag_retrieve", "noop"}:
            return {"id": step_id, "name": name, "type": str(mapped), "config": dict(config)}
        if mapped == "invoke_tool" or (mapped and "." in str(mapped)):
            return _invoke_tool_step(step_id, name, config, metadata=metadata or None)
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
    if node_type in {"decision", "if", "switch"}:
        decision_cfg = metadata.get("decisionConfig") if isinstance(metadata.get("decisionConfig"), dict) else {}
        if not decision_cfg and isinstance(config.get("decisionConfig"), dict):
            decision_cfg = config.get("decisionConfig")
        expression = (
            decision_cfg.get("conditions")
            or decision_cfg.get("expression")
            or config.get("expression")
            or config.get("condition")
            or ""
        )
        branches = decision_cfg.get("outputPaths") or decision_cfg.get("output_paths") or config.get("branches") or {}
        return {
            "id": step_id,
            "name": name,
            "type": "condition",
            "config": {
                "builder_node_type": node_type,
                "expression": expression,
                "strategy": decision_cfg.get("strategy") or config.get("strategy") or "rule-based",
                "branches": branches,
                "default_branch": decision_cfg.get("defaultPath")
                or decision_cfg.get("default_branch")
                or config.get("default_branch")
                or "default",
            },
            "metadata": metadata or {},
        }
    if node_type == "merge":
        return {
            "id": step_id,
            "name": name,
            "type": "noop",
            "config": {
                "builder_node_type": "merge",
                "merge_mode": config.get("merge_mode") or metadata.get("merge_mode") or "wait_all",
            },
            "metadata": {**(metadata or {}), "logic_node": "merge"},
        }
    if node_type == "loop":
        return {
            "id": step_id,
            "name": name,
            "type": "noop",
            "config": {
                "builder_node_type": "loop",
                "collection": config.get("collection") or metadata.get("collection"),
                "max_iterations": config.get("max_iterations") or metadata.get("max_iterations") or 10,
            },
            "metadata": {**(metadata or {}), "logic_node": "loop"},
        }
    if node_type in {"approval", "task"}:
        if node_type == "approval":
            return {
                "id": step_id,
                "name": name,
                "type": "approval",
                "config": dict(config),
                "metadata": metadata or {},
            }
        return {
            "id": step_id,
            "name": name,
            "type": "noop",
            "config": {"builder_node_type": node_type},
            "metadata": metadata or {"simulated": True},
        }
    return {"id": step_id, "name": name, "type": "noop", "config": dict(config)}


def prepare_builder_edge(edge: dict[str, Any], workflow_id: str, environment_name: str) -> dict[str, Any]:
    """Normalize canvas/contract edges so API responses always include id + workflow_id."""
    from_id = edge.get("from_node_id") or edge.get("from")
    to_id = edge.get("to_node_id") or edge.get("to")
    if not from_id or not to_id:
        raise ValueError("Builder edge missing from/to node ids")
    edge_id = edge.get("id") or f"{from_id}->{to_id}"
    return {
        **edge,
        "id": str(edge_id),
        "workflow_id": str(edge.get("workflow_id") or workflow_id),
        "environment": edge.get("environment") or environment_name,
        "from_node_id": str(from_id),
        "to_node_id": str(to_id),
    }


def _contract_builder_graph(client: Any, org_id: str, workflow_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    contract_row = (
        client.table("workflows")
        .select("nodes, edges")
        .eq("org_id", org_id)
        .eq("id", str(workflow_id))
        .limit(1)
        .execute()
    )
    if not contract_row.data:
        return [], []
    row = contract_row.data[0]
    contract_nodes = row.get("nodes") if isinstance(row.get("nodes"), list) else []
    contract_edges = row.get("edges") if isinstance(row.get("edges"), list) else []
    if not contract_nodes:
        return [], contract_edges
    return _builder_nodes_from_contract(contract_nodes, contract_edges)


def _builder_nodes_are_thin(nodes: list[dict[str, Any]]) -> bool:
    """True when canvas stubs lack config/metadata/instructions (marketplace thin contract)."""
    if not nodes:
        return True
    for node in nodes:
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
        description = str(node.get("description") or node.get("instruction") or "").strip()
        task = str(
            metadata.get("task")
            or config.get("task")
            or config.get("instruction")
            or config.get("instructions")
            or ""
        ).strip()
        action = str(
            config.get("action")
            or config.get("tool_action")
            or config.get("selectedAction")
            or config.get("selected_action")
            or ""
        ).strip()
        agent_id = str(
            metadata.get("agent_id")
            or metadata.get("agentId")
            or config.get("agent_id")
            or config.get("agentId")
            or ""
        ).strip()
        if description or task or action or agent_id or len(config) > 0 or len(metadata) > 0:
            return False
    return True


def bind_agent_seeds_on_builder_nodes(
    client: Any,
    org_id: str,
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve lingering ``agent_seed`` values against org agents (install / re-open)."""
    seeds: set[str] = set()
    for node in nodes:
        metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        agent_id = metadata.get("agent_id") or metadata.get("agentId") or config.get("agent_id")
        seed = metadata.get("agent_seed") or config.get("agent_seed")
        if seed and not agent_id:
            seeds.add(str(seed))
        next_seed = metadata.get("next_agent_seed")
        if next_seed and not (metadata.get("next_agent_id") or config.get("next_agent_id")):
            seeds.add(str(next_seed))
    if not seeds:
        return nodes

    by_seed: dict[str, str] = {}
    try:
        rows = (
            client.table("agents")
            .select("id, name, config")
            .eq("org_id", org_id)
            .limit(200)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("builder agent seed lookup skipped: %s", exc)
        return nodes

    for row in rows.data or []:
        agent_id = str(row.get("id") or "")
        if not agent_id:
            continue
        config = row.get("config") if isinstance(row.get("config"), dict) else {}
        slug = str(
            config.get("marketplaceSlug")
            or config.get("slug")
            or config.get("marketplace_slug")
            or ""
        ).strip()
        name = str(row.get("name") or "").strip().lower()
        if slug:
            by_seed[f"agent:{slug}"] = agent_id
            by_seed[slug] = agent_id
        if name:
            by_seed[f"agent:{name.replace(' ', '-')}"] = agent_id
            by_seed[name] = agent_id
        # Prospecting enrichment agent is installed with seed key = AGENT_SLUG only
        # via marketplace_entity_id(..., AGENT_SLUG) — also match common display names.
        if "lead enrichment" in name:
            by_seed["agent:lead-enrichment-coordinator"] = agent_id
            by_seed["lead-enrichment-coordinator"] = agent_id
        if "msp prospecting" in name or "prospecting coordinator" in name:
            by_seed["agent:msp-prospecting-coordinator"] = agent_id
            by_seed["msp-prospecting-coordinator"] = agent_id

    if not by_seed:
        return nodes

    hydrated: list[dict[str, Any]] = []
    for node in nodes:
        row = dict(node)
        metadata = dict(row.get("metadata") or {})
        config = dict(row.get("config") or {})
        seed = metadata.get("agent_seed") or config.get("agent_seed")
        if seed and not (metadata.get("agent_id") or config.get("agent_id")):
            seed_key = str(seed)
            slug = seed_key[6:] if seed_key.startswith("agent:") else seed_key
            resolved = by_seed.get(seed_key) or by_seed.get(slug)
            if resolved:
                metadata["agent_id"] = resolved
                config["agent_id"] = resolved
                config["agentId"] = resolved
                metadata.pop("agent_seed", None)
                config.pop("agent_seed", None)
        next_seed = metadata.get("next_agent_seed")
        if next_seed and not metadata.get("next_agent_id"):
            next_key = str(next_seed)
            next_slug = next_key[6:] if next_key.startswith("agent:") else next_key
            resolved_next = by_seed.get(next_key) or by_seed.get(next_slug)
            if resolved_next:
                metadata["next_agent_id"] = resolved_next
                metadata.pop("next_agent_seed", None)
        row["metadata"] = metadata
        row["config"] = config
        hydrated.append(row)
    return hydrated


def resolve_builder_graph(
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    wf: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load builder canvas from graph tables, falling back to contract JSON.

    Marketplace installs often leave thin ``workflows.nodes`` stubs. When those
    stubs lack config/metadata, prefer the rich ``workflow_defs.definition``.
    """
    from app.workflows.repository import list_workflow_edges, list_workflow_nodes

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    try:
        nodes = list_workflow_nodes(client, org_id, str(workflow_id), environment_name)
        edges = list_workflow_edges(client, org_id, str(workflow_id), environment_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("builder graph tables unavailable for %s: %s", workflow_id, exc)
        nodes = []
        edges = []

    definition = wf.get("definition") if isinstance(wf.get("definition"), dict) else {}
    definition_steps = definition.get("steps") if isinstance(definition.get("steps"), list) else []

    if not nodes:
        contract_nodes, contract_edges = _contract_builder_graph(client, org_id, workflow_id)
        if contract_nodes and not _builder_nodes_are_thin(contract_nodes):
            nodes, edges = contract_nodes, contract_edges
        elif definition_steps:
            nodes, edges = definition_to_builder_nodes(definition)
        elif contract_nodes:
            nodes, edges = contract_nodes, contract_edges
    elif _builder_nodes_are_thin(nodes) and definition_steps:
        # Persisted graph rows can also be thin stubs — recover from definition.
        nodes, edges = definition_to_builder_nodes(definition)
    elif not edges:
        _, contract_edges = _contract_builder_graph(client, org_id, workflow_id)
        if contract_edges:
            edges = contract_edges

    nodes = bind_agent_seeds_on_builder_nodes(client, org_id, nodes)

    for node in nodes:
        node["workflow_id"] = str(workflow_id)
        node["environment"] = environment_name

    prepared_edges: list[dict[str, Any]] = []
    for edge in edges:
        from_id = edge.get("from_node_id") or edge.get("from")
        to_id = edge.get("to_node_id") or edge.get("to")
        if not from_id or not to_id:
            continue
        try:
            prepared_edges.append(prepare_builder_edge(edge, str(workflow_id), environment_name))
        except ValueError:
            continue
    return nodes, prepared_edges


def definition_to_builder_nodes(definition: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Hydrate a canvas from stored step definitions (marketplace / pack installs)."""
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
        from app.workflows.definition_resolver import normalize_legacy_node_type

        mapped_type = normalize_legacy_node_type(step_type)
        node_metadata = dict(metadata)
        requires_connector = step.get("requires_connector")
        if mapped_type == "invoke_tool" or step_type == "invoke_tool":
            node_type = "connector"
            tool_config = dict(config)
            if tool_config.get("action") and not tool_config.get("tool_action"):
                tool_config["tool_action"] = tool_config["action"]
            if requires_connector:
                tool_config.setdefault("vendor", str(requires_connector))
                tool_config.setdefault("connector", str(requires_connector))
                tool_config.setdefault("requires_connector", str(requires_connector))
            action = str(tool_config.get("action") or tool_config.get("tool_action") or "")
            if action and "." in action and not tool_config.get("selectedAction"):
                vendor, selected = action.split(".", 1)
                tool_config.setdefault("vendor", vendor)
                tool_config.setdefault("selectedAction", selected)
                tool_config.setdefault("selected_action", selected)
        elif step_type in {"slack_post_message", "email_send", "webhook_post", "rag_retrieve"}:
            node_type = "tool"
            tool_config = dict(config)
        elif mapped_type == "approval":
            # GoalService/Meson emit human_approval — must not hydrate as task.
            node_type = "approval"
            tool_config = dict(config)
            node_metadata["has_approval_gate"] = True
        else:
            node_type = "agent" if step_type == "agent" else "task"
            tool_config = dict(config)

        task = str(node_metadata.get("task") or tool_config.get("task") or "").strip()
        instruction = str(
            tool_config.get("instruction")
            or tool_config.get("instructions")
            or step.get("instruction")
            or step.get("description")
            or ""
        ).strip()
        description = task or instruction
        if task:
            tool_config.setdefault("task", task)
            if node_type == "task":
                tool_config.setdefault("instruction", task)
                tool_config.setdefault("instructions", task)
        elif instruction and node_type in {"task", "connector", "tool"}:
            tool_config.setdefault("instruction", instruction)
            tool_config.setdefault("instructions", instruction)
        agent_id = node_metadata.get("agent_id") or node_metadata.get("agentId")
        if agent_id:
            tool_config.setdefault("agent_id", agent_id)
            tool_config.setdefault("agentId", agent_id)
        if node_metadata.get("agent_seed") and not agent_id:
            tool_config.setdefault("agent_seed", node_metadata.get("agent_seed"))

        nodes.append(
            {
                "id": step_id,
                "node_type": node_type,
                "title": str(step.get("name") or step_id),
                "name": str(step.get("name") or step_id),
                "description": description or None,
                "instruction": description or None,
                "config": tool_config,
                "metadata": node_metadata,
                "position": {"x": x, "y": 160 + (idx % 3) * 40},
                "position_x": x,
                "position_y": 160 + (idx % 3) * 40,
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
    try:
        client.table("workflow_edges").delete().eq("org_id", org_id).eq("workflow_id", workflow_id).eq(
            "environment", environment_name
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow_edges delete skipped for %s: %s", workflow_id, exc)
    try:
        client.table("workflow_nodes").delete().eq("org_id", org_id).eq("workflow_id", workflow_id).eq(
            "environment", environment_name
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow_nodes delete skipped for %s: %s", workflow_id, exc)


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
        canvas_type = str(raw.get("type") or raw.get("node_type") or "task")
        node_type, type_metadata = persist_node_type(canvas_type)
        config = raw.get("config") if isinstance(raw.get("config"), dict) else {}
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        if type_metadata:
            metadata = {**metadata, **type_metadata}
        if not metadata:
            for key in ("decisionConfig", "councilConfig", "outputPaths"):
                if key in raw:
                    metadata[key] = raw[key]
        if canvas_type == "approval":
            metadata = {**metadata, "has_approval_gate": True}
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
    wf_meta = (
        client.table("workflow_defs")
        .select("name, description, status, config, version, created_by")
        .eq("id", workflow_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    meta = dict(wf_meta.data[0]) if wf_meta.data else {}
    sync_legacy_workflow_to_contract(
        client,
        workflow_id=workflow_id,
        org_id=org_id,
        name=str(meta.get("name") or "Workflow"),
        description=meta.get("description"),
        status=meta.get("status"),
        definition=definition,
        config=meta.get("config") if isinstance(meta.get("config"), dict) else {},
        environment_name=environment_name,
        created_by=str(meta["created_by"]) if meta.get("created_by") else created_by,
        version=str(meta.get("version")) if meta.get("version") else None,
        nodes=contract_nodes_from_builder(stored_nodes),
        edges=contract_edges_from_builder(stored_edges),
    )
    return stored_nodes, stored_edges, definition
