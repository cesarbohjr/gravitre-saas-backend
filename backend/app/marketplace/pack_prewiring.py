"""Phase 2 — pack / workflow pre-wiring evaluation (distinct from connector install-ready)."""
from __future__ import annotations

from typing import Any

from app.marketplace.install_ready import (
    _declared_install_keys,
    _extract_workflow_steps,
    evaluate_binding_install_ready,
)
from app.marketplace.workflow_contract import steps_to_rich_contract
from app.workflows.builder_sync import definition_to_builder_nodes
from app.workflows.constants import SCHEMA_VERSION

MIN_AGENT_TASK_CHARS = 40

_STUB_FRAGMENTS = (
    "todo",
    "tbd",
    "placeholder",
    "lorem ipsum",
    "fill this in",
    "coming soon",
)


def definition_with_sequential_graph(
    steps: list[dict[str, Any]],
    *,
    schema_version: str = SCHEMA_VERSION,
) -> dict[str, Any]:
    """Embed declared sequential edges so Phase 0 canvas disconnect detection applies."""
    definition: dict[str, Any] = {"schema_version": schema_version, "steps": steps}
    nodes, edges = definition_to_builder_nodes(definition)
    definition["graph"] = {
        "nodes": [
            {
                "id": n.get("id"),
                "type": n.get("node_type") or n.get("type"),
                "name": n.get("name") or n.get("title"),
            }
            for n in nodes
        ],
        "edges": [
            {
                "from_node_id": e.get("from_node_id") or e.get("from"),
                "to_node_id": e.get("to_node_id") or e.get("to"),
            }
            for e in edges
            if (e.get("from_node_id") or e.get("from")) and (e.get("to_node_id") or e.get("to"))
        ],
    }
    return definition


def evaluate_pack_prewiring(asset: dict[str, Any]) -> dict[str, Any]:
    """Return pre-wiring verdict for one catalog asset (workflow-bearing types)."""
    asset_type = str(asset.get("asset_type") or "")
    slug = str(asset.get("slug") or "")
    steps, schema_version = _extract_workflow_steps(asset)
    binding = evaluate_binding_install_ready(asset)

    result: dict[str, Any] = {
        "slug": slug,
        "assetType": asset_type,
        "hasWorkflow": bool(steps),
        "stepCount": len(steps),
        "edgeCount": 0,
        "bindingOk": bool(binding["installReady"]),
        "bindingErrors": binding["installReadyErrors"],
        "errors": [],
        "manualSetupRequired": [],
        "verdict": "N_A",
    }
    if asset_type not in {"workflow", "department_pack", "intelligence_pack"}:
        return result
    if not steps:
        result["errors"].append(
            {
                "code": "prewiring.missing_workflow_steps",
                "message": "Published pack/workflow has no embedded steps",
            }
        )
        result["verdict"] = "FAIL"
        return result

    nodes, edges = steps_to_rich_contract(steps)
    result["edgeCount"] = len(edges)
    expected_edges = max(0, len(steps) - 1)
    if len(nodes) != len(steps):
        result["errors"].append(
            {
                "code": "prewiring.node_count_mismatch",
                "message": f"contract nodes={len(nodes)} steps={len(steps)}",
            }
        )
    if len(edges) != expected_edges:
        result["errors"].append(
            {
                "code": "prewiring.edge_topology",
                "message": f"expected {expected_edges} sequential edges, got {len(edges)}",
            }
        )
    if not binding["installReady"]:
        result["errors"].append(
            {
                "code": "prewiring.binding_failed",
                "message": "Phase 0 binding validator failed on pack workflow definition",
            }
        )

    from app.workflows.binding_validation import validate_bindings

    graph_def = definition_with_sequential_graph(steps, schema_version=schema_version)
    graph_check = validate_bindings(
        graph_def,
        declared_parameters=_declared_install_keys(asset),
    )
    if not graph_check.ok:
        for err in graph_check.errors:
            if err.code == "binding.canvas_graph_disconnected":
                result["errors"].append(err.as_dict())

    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("id") or "")
        if not str(step.get("name") or "").strip():
            result["errors"].append(
                {
                    "code": "prewiring.missing_label",
                    "message": f"step {step_id!r} missing name/label",
                    "stepId": step_id,
                }
            )
        step_type = str(step.get("type") or "")
        meta = step.get("metadata") if isinstance(step.get("metadata"), dict) else {}
        if step_type == "agent":
            task = str(meta.get("task") or "").strip()
            low = task.lower()
            if len(task) < MIN_AGENT_TASK_CHARS:
                result["errors"].append(
                    {
                        "code": "prewiring.stub_agent_task",
                        "message": (
                            f"agent step {step_id!r} task is too short "
                            f"({len(task)} < {MIN_AGENT_TASK_CHARS})"
                        ),
                        "stepId": step_id,
                    }
                )
            elif any(frag in low for frag in _STUB_FRAGMENTS):
                result["errors"].append(
                    {
                        "code": "prewiring.placeholder_agent_task",
                        "message": f"agent step {step_id!r} looks like a placeholder",
                        "stepId": step_id,
                    }
                )
            if not meta.get("agent_seed") and not meta.get("agent_id"):
                result["errors"].append(
                    {
                        "code": "prewiring.missing_agent_seed",
                        "message": f"agent step {step_id!r} missing agent_seed/agent_id",
                        "stepId": step_id,
                    }
                )
            receiver = str(meta.get("receiver_task") or "").strip()
            if meta.get("next_agent_seed") and receiver and len(receiver) < MIN_AGENT_TASK_CHARS:
                result["errors"].append(
                    {
                        "code": "prewiring.stub_receiver_task",
                        "message": f"receiver_task on {step_id!r} too short",
                        "stepId": step_id,
                    }
                )
        if step_type == "invoke_tool":
            cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
            action = str(cfg.get("action") or cfg.get("tool_action") or "").strip()
            if "." not in action:
                result["errors"].append(
                    {
                        "code": "prewiring.missing_tool_action",
                        "message": f"tool step {step_id!r} missing vendor.action",
                        "stepId": step_id,
                    }
                )
            if not step.get("requires_connector"):
                result["errors"].append(
                    {
                        "code": "prewiring.missing_requires_connector",
                        "message": f"tool step {step_id!r} missing requires_connector",
                        "stepId": step_id,
                    }
                )

    for row in asset.get("required_connectors") or []:
        if not isinstance(row, dict) or not bool(row.get("required", True)):
            continue
        ctype = str(row.get("connectorType") or row.get("connector_type") or "").strip()
        if ctype:
            result["manualSetupRequired"].append(
                {
                    "kind": "connect_account",
                    "connector": ctype,
                    "reason": f"Connect {ctype} before running this pack",
                }
            )
    for row in asset.get("install_variables") or []:
        if not isinstance(row, dict) or not bool(row.get("required", False)):
            continue
        key = str(row.get("key") or "").strip()
        if key:
            result["manualSetupRequired"].append(
                {
                    "kind": "install_variable",
                    "key": key,
                    "reason": str(row.get("description") or row.get("label") or key),
                }
            )

    result["verdict"] = "PASS" if not result["errors"] else "FAIL"
    return result


def materialize_pack_canvas_graph(
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    steps: list[dict[str, Any]],
    created_by: str | None,
) -> None:
    """Persist builder nodes/edges via sync_builder_graph (same gate as canvas save)."""
    from app.workflows.builder_sync import sync_builder_graph

    contract_nodes, contract_edges = steps_to_rich_contract(steps)
    builder_edges = [
        {
            "from_node_id": e.get("from") or e.get("from_node_id"),
            "to_node_id": e.get("to") or e.get("to_node_id"),
        }
        for e in contract_edges
    ]
    sync_builder_graph(
        client,
        org_id=org_id,
        workflow_id=workflow_id,
        environment_name=environment_name,
        nodes=contract_nodes,
        edges=builder_edges,
        created_by=created_by,
    )
