"""STA-135 / AI-005: Graph-native workflow execution engine.

Executes builder graphs (nodes + edges) in topological batches so each node
receives full upstream outputs before it runs. Integrates with the same run/step
logging primitives as ``execute.py``.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.connectors.rate_limit import RateLimitError
from app.core.logging import get_logger, request_id_ctx
from app.services.agent_interrupt_service import AgentExecutionInterrupted, enforce_interrupt
from app.services.council_workflow_service import resolve_active_branch, should_skip_for_branch
from app.workflows.audit import write_audit_event
from app.workflows.builder_sync import _node_to_step
from app.workflows.constants import (
    ERROR_CODE_EMAIL_FAILED,
    ERROR_CODE_RAG_UNAVAILABLE,
    ERROR_CODE_RATE_LIMITED,
    ERROR_CODE_SLACK_FAILED,
    ERROR_CODE_STEP_FAILED,
    ERROR_CODE_VALIDATION,
    ERROR_CODE_WEBHOOK_FAILED,
    RESOURCE_TYPE_WORKFLOW_RUN,
    RUN_STATUS_CANCELLED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_PAUSED,
    STEP_STATUS_COMPLETED,
    STEP_STATUS_FAILED,
    STEP_STATUS_SKIPPED,
)
from app.workflows.registry import StepContext, get_handler
from app.workflows.repository import (
    create_step,
    emit_execute_completed,
    emit_execute_failed,
    emit_execute_step_completed,
    emit_execute_step_failed,
    get_run_with_steps,
    set_step_running,
    update_run,
    update_step,
)

logger = get_logger(__name__)

_PASSTHROUGH_NODE_TYPES = frozenset({"source", "trigger"})


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


def execute_workflow_graph(
    settings: Settings,
    org_id: str,
    user_id: str,
    run_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    parameters: dict[str, Any],
    client: Any,
    environment_name: str = "default",
    steps_exist: bool = False,
) -> tuple[str, list[dict], list[str], bool]:
    """Execute a builder graph in topological batches with upstream context."""
    graph = build_execution_graph(nodes, edges)
    validate_execution_graph(graph)
    batches = topological_batches(graph)

    node_outputs: dict[str, Any] = {}
    errors: list[str] = []
    run_failed = False
    run_paused = False
    run_cancelled = False
    run_error_message: str | None = None
    rate_limited = False
    step_index = 0

    edge_dicts = _edges_as_dicts(graph.edges)
    for batch in batches:
        for node_id in batch:
            try:
                enforce_interrupt(client, org_id, "workflow_run", run_id, actor_id=user_id)
            except AgentExecutionInterrupted as exc:
                if exc.signal == "pause":
                    run_paused = True
                else:
                    run_cancelled = True
                    run_failed = True
                    run_error_message = "Interrupted by operator"
                    errors.append(run_error_message)
                break

            node = graph.nodes_by_id[node_id]
            step_def = _node_to_step(node, graph.nodes_by_id, edge_dicts)
            if step_def is None:
                node_outputs[node_id] = {"passthrough": True, "node_type": node.get("node_type")}
                continue

            step_id = str(step_def["id"])
            step_name = str(step_def.get("name") or step_id)
            step_type = str(step_def["type"])
            config = dict(step_def.get("config") or {})
            if isinstance(step_def.get("metadata"), dict):
                config["metadata"] = step_def["metadata"]

            upstream = _upstream_outputs(graph, node_id, node_outputs)
            merged_parameters = {**parameters, "upstream_outputs": upstream}

            created = create_step(
                client=client,
                run_id=run_id,
                org_id=org_id,
                step_id=step_id,
                step_index=step_index,
                step_name=step_name,
                step_type=step_type,
            )
            step_uuid = str(created["id"])
            step_started = datetime.now(timezone.utc).isoformat()
            set_step_running(client, step_uuid, step_started)

            active_branch = resolve_active_branch(node_outputs)
            if should_skip_for_branch(config, active_branch):
                skipped_output = {
                    "skipped": True,
                    "reason": "branch_mismatch",
                    "when_branch": config.get("when_branch"),
                    "active_branch": active_branch,
                    "upstream_outputs": upstream,
                }
                node_outputs[node_id] = skipped_output
                update_step(
                    client=client,
                    step_uuid=step_uuid,
                    status=STEP_STATUS_SKIPPED,
                    output_snapshot=skipped_output,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
                emit_execute_step_completed(client, org_id, user_id, run_id, step_index, step_id)
                step_index += 1
                continue

            try:
                handler = get_handler(step_type)
                if not handler.supports_execute:
                    raise ValueError(f"Invalid step type for execute: {step_type}")
                context = StepContext(
                    settings=settings,
                    org_id=org_id,
                    user_id=user_id,
                    run_id=run_id,
                    environment_name=environment_name,
                    step_id=step_id,
                    step_type=step_type,
                    step_index=step_index,
                    config=config,
                    parameters=merged_parameters,
                    step_outputs=dict(node_outputs),
                    client=client,
                    is_dry_run=False,
                )
                output = handler.execute(context)
                if isinstance(output, dict):
                    output = {**output, "upstream_outputs": upstream}
                else:
                    output = {"result": output, "upstream_outputs": upstream}
                node_outputs[node_id] = output
                completed_at = datetime.now(timezone.utc).isoformat()
                duration_ms = int(
                    (datetime.fromisoformat(completed_at) - datetime.fromisoformat(step_started)).total_seconds() * 1000
                )
                update_step(
                    client=client,
                    step_uuid=step_uuid,
                    status=STEP_STATUS_COMPLETED,
                    output_snapshot=output,
                    completed_at=completed_at,
                )
                emit_execute_step_completed(client, org_id, user_id, run_id, step_index, step_id)
                write_audit_event(
                    client,
                    org_id,
                    user_id,
                    action="workflow.execute.step_timing",
                    resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                    resource_id=run_id,
                    metadata={
                        "step_id": step_id,
                        "node_id": node_id,
                        "step_type": step_type,
                        "duration_ms": duration_ms,
                        "execution_mode": "graph",
                    },
                )
                logger.info(
                    "workflow_graph_step_completed request_id=%s org_id=%s run_id=%s node_id=%s step_id=%s duration_ms=%s",
                    request_id_ctx.get(),
                    org_id,
                    run_id,
                    node_id,
                    step_id,
                    duration_ms,
                )
            except RateLimitError as exc:
                rate_limited = True
                run_failed = True
                run_error_message = "Rate limit exceeded"
                _fail_step(
                    client,
                    step_uuid=step_uuid,
                    step_started=step_started,
                    code=ERROR_CODE_RATE_LIMITED,
                    message=run_error_message,
                    org_id=org_id,
                    user_id=user_id,
                    run_id=run_id,
                    step_index=step_index,
                    step_id=step_id,
                    step_type=step_type,
                    node_id=node_id,
                )
                errors.append(str(exc))
                break
            except ValueError as exc:
                run_failed = True
                run_error_message = "Step validation failed"
                _fail_step(
                    client,
                    step_uuid=step_uuid,
                    step_started=step_started,
                    code=ERROR_CODE_VALIDATION,
                    message=str(exc)[:500],
                    org_id=org_id,
                    user_id=user_id,
                    run_id=run_id,
                    step_index=step_index,
                    step_id=step_id,
                    step_type=step_type,
                    node_id=node_id,
                )
                errors.append(str(exc))
                break
            except Exception:
                run_failed = True
                if "rag" in step_type.lower():
                    run_error_message = "Retrieval temporarily unavailable"
                    code = ERROR_CODE_RAG_UNAVAILABLE
                elif "slack" in step_type.lower():
                    run_error_message = "Slack send failed"
                    code = ERROR_CODE_SLACK_FAILED
                elif "email" in step_type.lower():
                    run_error_message = "Email send failed"
                    code = ERROR_CODE_EMAIL_FAILED
                elif "webhook" in step_type.lower():
                    run_error_message = "Webhook send failed"
                    code = ERROR_CODE_WEBHOOK_FAILED
                else:
                    run_error_message = "Step execution failed"
                    code = ERROR_CODE_STEP_FAILED
                _fail_step(
                    client,
                    step_uuid=step_uuid,
                    step_started=step_started,
                    code=code,
                    message=run_error_message,
                    org_id=org_id,
                    user_id=user_id,
                    run_id=run_id,
                    step_index=step_index,
                    step_id=step_id,
                    step_type=step_type,
                    node_id=node_id,
                )
                errors.append(run_error_message)
                break

            step_index += 1

        if run_failed or run_paused or run_cancelled:
            break

    if run_paused:
        final_status = RUN_STATUS_PAUSED
    elif run_cancelled:
        final_status = RUN_STATUS_CANCELLED
    elif run_failed:
        final_status = RUN_STATUS_FAILED
    else:
        final_status = RUN_STATUS_COMPLETED

    run_with_steps = get_run_with_steps(client, org_id, run_id, environment_name)
    step_rows = run_with_steps["steps"] if run_with_steps else []
    completed_at_iso = datetime.now(timezone.utc).isoformat()
    update_run(
        client=client,
        run_id=run_id,
        status=final_status,
        completed_at=completed_at_iso,
        error_message=run_error_message,
    )
    if run_failed:
        emit_execute_failed(client, org_id, user_id, run_id, run_error_message)
    else:
        emit_execute_completed(client, org_id, user_id, run_id, final_status)

    return final_status, step_rows, errors, rate_limited


def _fail_step(
    *,
    client: Any,
    step_uuid: str,
    step_started: str,
    code: str,
    message: str,
    org_id: str,
    user_id: str,
    run_id: str,
    step_index: int,
    step_id: str,
    step_type: str,
    node_id: str,
) -> None:
    duration_ms = int(
        (datetime.now(timezone.utc) - datetime.fromisoformat(step_started)).total_seconds() * 1000
    )
    update_step(
        client=client,
        step_uuid=step_uuid,
        status=STEP_STATUS_FAILED,
        error_code=code,
        error_message=message,
        is_retryable=code == ERROR_CODE_RAG_UNAVAILABLE,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    emit_execute_step_failed(client, org_id, user_id, run_id, step_index, step_id, code)
    write_audit_event(
        client,
        org_id,
        user_id,
        action="workflow.execute.step_timing",
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={
            "step_id": step_id,
            "node_id": node_id,
            "step_type": step_type,
            "duration_ms": duration_ms,
            "execution_mode": "graph",
            "error_code": code,
        },
    )
