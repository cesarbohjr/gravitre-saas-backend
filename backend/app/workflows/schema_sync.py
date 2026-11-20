"""STA-271 Phase C: dual-write sync between legacy and contract workflow tables."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.workflows.constants import SCHEMA_VERSION
from app.workflows.run_status_contract import contract_run_status_v2, run_status_metadata

logger = logging.getLogger(__name__)

_LEGACY_TO_CONTRACT_WORKFLOW_STATUS = {
    "enabled": "active",
    "disabled": "paused",
    "inactive": "paused",
    "active": "active",
    "draft": "draft",
    "paused": "paused",
    "archived": "archived",
    "error": "error",
}

_CONTRACT_TO_LEGACY_WORKFLOW_STATUS = {
    "active": "active",
    "paused": "disabled",
    "draft": "draft",
    "archived": "archived",
    "error": "error",
}

_LEGACY_TO_CONTRACT_STEP_STATUS = {
    "pending": "pending",
    "running": "running",
    "completed": "completed",
    "success": "completed",
    "failed": "failed",
    "error": "failed",
    "skipped": "skipped",
}

_LEGACY_TO_CONTRACT_APPROVAL_STATUS = {
    "pending_approval": "pending",
    "pending": "pending",
    "approved": "approved",
    "rejected": "rejected",
    "not_required": "not_required",
}


def contract_workflow_status(legacy_status: str | None) -> str:
    raw = str(legacy_status or "draft").lower()
    if raw in {"draft", "active", "paused", "archived", "error"}:
        return raw
    return _LEGACY_TO_CONTRACT_WORKFLOW_STATUS.get(raw, "draft")


def legacy_workflow_status(contract_status: str | None) -> str:
    raw = str(contract_status or "draft").lower()
    return _CONTRACT_TO_LEGACY_WORKFLOW_STATUS.get(raw, raw if raw in {"draft", "active", "disabled", "archived"} else "draft")


def contract_run_status(legacy_status: str | None) -> str:
    return contract_run_status_v2(legacy_status)


def contract_step_status(legacy_status: str | None) -> str:
    raw = str(legacy_status or "pending").lower()
    return _LEGACY_TO_CONTRACT_STEP_STATUS.get(raw, "pending")


def contract_approval_status(legacy_status: str | None) -> str:
    raw = str(legacy_status or "not_required").lower()
    return _LEGACY_TO_CONTRACT_APPROVAL_STATUS.get(raw, "not_required")


def _graph_from_definition(definition: dict | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from app.workflows.builder_sync import definition_to_builder_nodes

    if not isinstance(definition, dict):
        return [], []
    graph = definition.get("graph")
    if isinstance(graph, dict):
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        if nodes:
            return [dict(n) for n in nodes if isinstance(n, dict)], [dict(e) for e in edges if isinstance(e, dict)]
    return definition_to_builder_nodes(definition)


def contract_nodes_from_builder(stored_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from app.workflows.builder_sync import restore_node_type

    nodes: list[dict[str, Any]] = []
    for node in stored_nodes:
        nodes.append(
            {
                "id": str(node.get("id")),
                "type": restore_node_type(node),
                "name": node.get("name") or node.get("title") or str(node.get("id")),
                "title": node.get("title") or node.get("name"),
                "config": node.get("config") or {},
                "position": node.get("position")
                or {"x": node.get("position_x") or 0, "y": node.get("position_y") or 0},
            }
        )
    return nodes


def contract_edges_from_builder(stored_edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for edge in stored_edges:
        from_id = edge.get("from_node_id") or edge.get("from")
        to_id = edge.get("to_node_id") or edge.get("to")
        if not from_id or not to_id:
            continue
        edges.append({"from": str(from_id), "to": str(to_id)})
    return edges


def contract_nodes_edges_from_definition(definition: dict | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    builder_nodes, builder_edges = _graph_from_definition(definition)
    if not builder_nodes and isinstance(definition, dict):
        steps = definition.get("steps") if isinstance(definition.get("steps"), list) else []
        if steps:
            nodes = [
                {
                    "id": str(step.get("id")),
                    "type": step.get("type") or "task",
                    "name": step.get("name") or str(step.get("id")),
                }
                for step in steps
                if isinstance(step, dict) and step.get("id")
            ]
            edges = [
                {"from": str(steps[i]["id"]), "to": str(steps[i + 1]["id"])}
                for i in range(len(steps) - 1)
                if isinstance(steps[i], dict) and isinstance(steps[i + 1], dict) and steps[i].get("id") and steps[i + 1].get("id")
            ]
            return nodes, edges
    return contract_nodes_from_builder(builder_nodes), contract_edges_from_builder(builder_edges)


def _builder_nodes_from_contract(nodes: list[Any], edges: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    builder_nodes: list[dict[str, Any]] = []
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        node_id = raw.get("id")
        if not node_id:
            continue
        position = raw.get("position") if isinstance(raw.get("position"), dict) else {}
        config = raw.get("config") if isinstance(raw.get("config"), dict) else {}
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        agent_id = raw.get("agent_id") or raw.get("agentId")
        if agent_id and "agent_id" not in metadata:
            metadata = {**metadata, "agent_id": agent_id}
        if agent_id and "agent_id" not in config:
            config = {**config, "agent_id": agent_id}
        builder_nodes.append(
            {
                "id": str(node_id),
                "node_type": raw.get("node_type") or raw.get("type") or "task",
                "title": raw.get("title") or raw.get("name") or str(node_id),
                "name": raw.get("name") or raw.get("title") or str(node_id),
                "description": raw.get("description"),
                "config": config,
                "metadata": metadata or None,
                "position": position,
                "position_x": position.get("x") if isinstance(position, dict) else raw.get("position_x") or 0,
                "position_y": position.get("y") if isinstance(position, dict) else raw.get("position_y") or 0,
            }
        )
    builder_edges: list[dict[str, Any]] = []
    for raw in edges:
        if not isinstance(raw, dict):
            continue
        from_id = raw.get("from_node_id") or raw.get("from")
        to_id = raw.get("to_node_id") or raw.get("to")
        if not from_id or not to_id:
            continue
        builder_edges.append({"from_node_id": str(from_id), "to_node_id": str(to_id)})
    return builder_nodes, builder_edges


def definition_from_contract_row(row: dict[str, Any]) -> dict[str, Any]:
    from app.workflows.builder_sync import graph_to_definition

    nodes = row.get("nodes") if isinstance(row.get("nodes"), list) else []
    edges = row.get("edges") if isinstance(row.get("edges"), list) else []
    if nodes:
        builder_nodes, builder_edges = _builder_nodes_from_contract(nodes, edges)
        if builder_nodes:
            return graph_to_definition(builder_nodes, builder_edges)
    return {"schema_version": SCHEMA_VERSION, "steps": []}


def contract_row_to_legacy_def(row: dict[str, Any]) -> dict[str, Any]:
    definition = definition_from_contract_row(row)
    return {
        "id": row.get("id"),
        "org_id": row.get("org_id"),
        "name": row.get("name"),
        "description": row.get("description"),
        "status": legacy_workflow_status(row.get("status")),
        "definition": definition,
        "schema_version": SCHEMA_VERSION,
        "version": row.get("version") or "v1.0.0",
        "updated_at": row.get("updated_at"),
        "created_at": row.get("created_at"),
        "goal": row.get("goal"),
        "stage": row.get("stage") or "build",
    }


def sync_legacy_workflow_to_contract(
    client: Any,
    *,
    workflow_id: str,
    org_id: str,
    name: str,
    description: str | None = None,
    status: str | None = None,
    definition: dict | None = None,
    config: dict | None = None,
    environment_name: str = "production",
    created_by: str | None = None,
    version: str | None = None,
    nodes: list | None = None,
    edges: list | None = None,
) -> None:
    """C.1: Mirror workflow_defs row into workflows."""
    try:
        contract_nodes = nodes
        contract_edges = edges
        if contract_nodes is None or contract_edges is None:
            derived_nodes, derived_edges = contract_nodes_edges_from_definition(definition)
            contract_nodes = contract_nodes if contract_nodes is not None else derived_nodes
            contract_edges = contract_edges if contract_edges is not None else derived_edges
        row: dict[str, Any] = {
            "id": workflow_id,
            "org_id": org_id,
            "name": name,
            "description": description,
            "status": contract_workflow_status(status),
            "environment": environment_name or "production",
            "nodes": contract_nodes or [],
            "edges": contract_edges or [],
            "config": config or {},
        }
        if version:
            row["version"] = version
        if created_by:
            row["created_by"] = created_by
        client.table("workflows").upsert(row, on_conflict="id").execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "schema_sync legacy->contract failed workflow_id=%s error=%s",
            workflow_id,
            exc,
        )


def sync_contract_workflow_to_legacy(
    client: Any,
    *,
    workflow_id: str,
    org_id: str,
    environment_name: str = "production",
) -> bool:
    """C.2: Mirror workflows row into workflow_defs."""
    from app.config import get_settings

    if not get_settings().workflow_legacy_writes:
        return False
    try:
        result = (
            client.table("workflows")
            .select("*")
            .eq("id", workflow_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return False
        row = dict(result.data[0])
        definition = definition_from_contract_row(row)
        payload: dict[str, Any] = {
            "id": workflow_id,
            "org_id": org_id,
            "name": row.get("name") or "Workflow",
            "description": row.get("description"),
            "status": legacy_workflow_status(row.get("status")),
            "definition": definition,
            "schema_version": SCHEMA_VERSION,
            "stage": row.get("stage") or "build",
            "version": row.get("version") or "v1.0.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        config = row.get("config")
        if isinstance(config, dict) and config:
            payload["config"] = config
        if row.get("created_by"):
            payload["created_by"] = row.get("created_by")
        client.table("workflow_defs").upsert(payload, on_conflict="id").execute()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "schema_sync contract->legacy failed workflow_id=%s environment=%s error=%s",
            workflow_id,
            environment_name,
            exc,
        )
        return False


def _duration_ms(started_at: str | None, completed_at: str | None) -> int | None:
    if not started_at or not completed_at:
        return None
    try:
        start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
        return max(int((end - start).total_seconds() * 1000), 0)
    except (TypeError, ValueError):
        return None


def mirror_legacy_run_to_contract(client: Any, run_id: str) -> bool:
    """Refresh intentional run/step projections from locked database sources.

    A stale application snapshot must never replace newer contract truth. The
    RPC does the read and both writes together, preserving unrelated metadata.
    Missing RPCs and partial acknowledgements fail; no client-upsert fallback.
    Canonical terminal finalization invokes this refresh inside its transaction.
    Other existing repository callers can retry this idempotent refresh.
    """
    try:
        result = client.rpc("refresh_workflow_run_projection", {"p_run_id": run_id}).execute()
        if result.data is not True:
            raise RuntimeError("run projection refresh was not acknowledged")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("schema_sync run mirror failed run_id=%s error=%s", run_id, type(exc).__name__)
        return False


def mirror_legacy_workflow_row_to_contract(
    client: Any,
    legacy_row: dict[str, Any],
    *,
    environment_name: str = "production",
    nodes: list | None = None,
    edges: list | None = None,
) -> None:
    """Convenience wrapper for a freshly inserted/updated workflow_defs row."""
    sync_legacy_workflow_to_contract(
        client,
        workflow_id=str(legacy_row["id"]),
        org_id=str(legacy_row["org_id"]),
        name=str(legacy_row.get("name") or "Workflow"),
        description=legacy_row.get("description"),
        status=legacy_row.get("status"),
        definition=legacy_row.get("definition") if isinstance(legacy_row.get("definition"), dict) else None,
        config=legacy_row.get("config") if isinstance(legacy_row.get("config"), dict) else None,
        environment_name=environment_name,
        created_by=str(legacy_row["created_by"]) if legacy_row.get("created_by") else None,
        version=str(legacy_row.get("version")) if legacy_row.get("version") else None,
        nodes=nodes,
        edges=edges,
    )
