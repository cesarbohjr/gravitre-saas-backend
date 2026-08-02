"""Graph execution runtime: parallel batches, approval pause, per-node policies (STA-136/139/140)."""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    RUN_STATUS_AWAITING_APPROVAL,
    RUN_STATUS_CANCELLED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_PAUSED,
    STEP_STATUS_COMPLETED,
    STEP_STATUS_FAILED,
    STEP_STATUS_SKIPPED,
)
from app.workflows.execution_engine import (
    ExecutionGraph,
    GraphValidationError,
    _APPROVAL_NODE_TYPES,
    _CHECKPOINT_KEY,
    _PASSTHROUGH_NODE_TYPES,
    _edges_as_dicts,
    _upstream_outputs,
    build_execution_graph,
    topological_batches,
    validate_execution_graph,
)
from app.workflows.registry import StepContext, get_handler
from app.workflows.repository import (
    create_step,
    emit_execute_step_completed,
    emit_execute_step_failed,
    get_run_with_steps,
    merge_run_parameters,
    set_step_running,
    update_run,
    update_step,
)

logger = get_logger(__name__)


@dataclass
class _NodeRunResult:
    node_id: str
    step_index: int
    halt: str | None = None  # failed | paused | cancelled | awaiting_approval
    error: str | None = None
    rate_limited: bool = False


@dataclass
class _GraphRunContext:
    settings: Settings
    org_id: str
    user_id: str
    run_id: str
    graph: ExecutionGraph
    edge_dicts: list[dict[str, Any]]
    parameters: dict[str, Any]
    client: Any
    environment_name: str
    node_outputs: dict[str, Any]
    skipped_nodes: list[str]
    step_index: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


def _node_policy(node: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
    on_failure = str(config.get("on_failure") or metadata.get("onFailure") or "fail_workflow").lower()
    if on_failure not in {"retry", "skip", "fail_workflow"}:
        on_failure = "fail_workflow"
    on_reject = str(config.get("on_reject") or metadata.get("onReject") or "fail_workflow").lower()
    if on_reject not in {"fail_workflow", "skip", "route_upstream"}:
        on_reject = "fail_workflow"
    return {
        "on_failure": on_failure,
        "max_retries": max(1, int(config.get("max_retries") or metadata.get("maxRetries") or 1)),
        "retry_backoff_ms": max(0, int(config.get("retry_backoff_ms") or metadata.get("retryBackoffMs") or 200)),
        "on_reject": on_reject,
        "reject_route_node_id": metadata.get("reject_route_node_id") or metadata.get("rejectRouteNodeId"),
    }


def _is_approval_node(node: dict[str, Any]) -> bool:
    node_type = str(node.get("node_type") or node.get("type") or "")
    return node_type in _APPROVAL_NODE_TYPES or bool(node.get("has_approval_gate"))


def _build_execution_log(
    *,
    node_id: str,
    step_type: str,
    upstream: dict[str, Any],
    config: dict[str, Any],
    output: dict[str, Any] | None,
    duration_ms: int,
    error_code: str | None = None,
    error_message: str | None = None,
    attempts: int = 1,
) -> str:
    payload = {
        "node_id": node_id,
        "step_type": step_type,
        "duration_ms": duration_ms,
        "attempts": attempts,
        "input": {"upstream_outputs": upstream, "config": config},
        "output": output,
        "model": (output or {}).get("model"),
        "tokens": (output or {}).get("tokens") or (output or {}).get("usage"),
        "error_code": error_code,
        "error_message": error_message,
    }
    return json.dumps(payload, default=str)[:8000]


def _finalize_run(
    ctx: _GraphRunContext,
    *,
    final_status: str,
    errors: list[str],
    run_error_message: str | None,
    rate_limited: bool,
) -> tuple[str, list[dict], list[str], bool]:
    run_with_steps = get_run_with_steps(ctx.client, ctx.org_id, ctx.run_id, ctx.environment_name)
    step_rows = run_with_steps["steps"] if run_with_steps else []
    workflow_id = str((run_with_steps or {}).get("workflow_id") or "") or None

    from app.services.execution_outcome import (
        VerifiedOutputRef,
        finalize_execution_outcome,
        is_terminal_run_status,
    )

    if is_terminal_run_status(final_status):
        wf_name = "Workflow"
        email_context = None
        channel_hints = {"bell": True, "email": False}
        if final_status == RUN_STATUS_COMPLETED:
            channel_hints = {"bell": True, "email": True}
            try:
                if workflow_id:
                    wf_row = (
                        ctx.client.table("workflow_defs")
                        .select("name")
                        .eq("org_id", ctx.org_id)
                        .eq("id", workflow_id)
                        .limit(1)
                        .execute()
                    )
                    if wf_row.data:
                        wf_name = str(wf_row.data[0].get("name") or wf_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workflow name lookup skipped run_id=%s error=%s", ctx.run_id, exc)
            email_context = {
                "kind": "workflow_completion",
                "run_id": ctx.run_id,
                "workflow_name": wf_name,
                "final_status": final_status,
            }

        outcome_source = "canvas" if (ctx.parameters or {}).get("source") == "canvas" else "api"
        from app.services.connector_output_refs import (
            collect_connector_output_refs,
            primary_vendor_url,
        )
        from app.services.connector_outcome_effects import (
            coerce_terminal_status_for_effect,
            is_mutating_action,
        )

        output_refs = collect_connector_output_refs(step_rows)
        vendor_url = primary_vendor_url(output_refs)
        # Downgrade empty-shell / unproven mutating writes at run level (same honesty
        # gate chat connector uses) so COMPLETED is not sold for Apollo/HubSpot list shells.
        coerced_status = final_status
        if final_status == RUN_STATUS_COMPLETED and output_refs:
            mutating_effects = [
                str(ref.get("outcome_effect") or "")
                for ref in output_refs
                if is_mutating_action(str(ref.get("invoke_action") or ""))
            ]
            if mutating_effects and all(
                effect in {"already_existed", "noop", "accepted_async", "unknown"}
                for effect in mutating_effects
            ):
                worst = next(
                    (
                        effect
                        for effect in mutating_effects
                        if effect in {"already_existed", "noop", "accepted_async", "unknown"}
                    ),
                    "unknown",
                )
                coerced_status = coerce_terminal_status_for_effect(
                    status=final_status,
                    effect=worst or "unknown",
                    invoke_action=next(
                        (
                            str(ref.get("invoke_action"))
                            for ref in output_refs
                            if is_mutating_action(str(ref.get("invoke_action") or ""))
                        ),
                        None,
                    ),
                )

        finalize_summary = (
            run_error_message
            if coerced_status == RUN_STATUS_FAILED
            else (
                "; ".join(
                    str(ref.get("summary"))
                    for ref in output_refs
                    if ref.get("summary")
                )[:2000]
                or f"Run finished with status {coerced_status}."
            )
        )
        finalize_execution_outcome(
            ctx.client,
            org_id=ctx.org_id,
            status=coerced_status,
            source=outcome_source,
            actor_id=ctx.user_id,
            run_id=ctx.run_id,
            workflow_id=workflow_id,
            error_summary=run_error_message,
            verified_output=VerifiedOutputRef(
                result_url=f"/runs/{ctx.run_id}",
                external_url=vendor_url,
                entity_type="workflow_run",
                entity_id=ctx.run_id,
                integration=next(
                    (str(ref.get("integration")) for ref in output_refs if ref.get("integration")),
                    None,
                ),
                summary=finalize_summary,
            ),
            channel_hints=channel_hints,
            email_context=email_context,
            metadata={
                "path": "execution_engine_runtime",
                "environment": ctx.environment_name,
                "step_results": output_refs,
                "connector_output_refs": output_refs,
            },
        )
        final_status = coerced_status
        if final_status == RUN_STATUS_COMPLETED:
            try:
                from app.marketplace.adoption import maybe_record_workflow_adoption

                maybe_record_workflow_adoption(
                    ctx.client,
                    org_id=ctx.org_id,
                    run_id=ctx.run_id,
                    final_status=final_status,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "marketplace adoption hook skipped org_id=%s run_id=%s error=%s",
                    ctx.org_id,
                    ctx.run_id,
                    str(exc),
                )
        if final_status in {RUN_STATUS_COMPLETED, RUN_STATUS_FAILED}:
            try:
                from app.services.agent_memory_service import create_agent_memory

                run_meta = run_with_steps or {}
                wf_id = str(run_meta.get("workflow_id") or "")
                params = run_meta.get("parameters") if isinstance(run_meta.get("parameters"), dict) else {}
                agent_id = str(params.get("agent_id") or params.get("agentId") or "")
                if wf_id and agent_id:
                    insight = f"Run {ctx.run_id} finished with status {final_status}."
                    if errors:
                        insight += f" Errors: {'; '.join(errors[:3])}"
                    create_agent_memory(
                        ctx.settings,
                        ctx.client,
                        ctx.org_id,
                        agent_id,
                        user_id=ctx.user_id or None,
                        content=f"Workflow {wf_id} outcome={final_status}: {insight}",
                        category="pattern",
                        provenance="outcome_learning",
                        confidence=70,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "workflow_outcome_learning_skipped org_id=%s run_id=%s error=%s",
                    ctx.org_id,
                    ctx.run_id,
                    exc,
                )
    else:
        update_run(
            client=ctx.client,
            run_id=ctx.run_id,
            status=final_status,
            completed_at=None,
            error_message=run_error_message,
        )
    return final_status, step_rows, errors, rate_limited


def _save_graph_checkpoint(
    ctx: _GraphRunContext,
    *,
    paused_at_node: str,
    batch_index: int,
    approval_context: dict[str, Any] | None = None,
    pause_reason: str | None = None,
) -> dict[str, Any]:
    checkpoint = {
        "paused_at_node": paused_at_node,
        "batch_index": batch_index,
        "step_index": ctx.step_index,
        "node_outputs": ctx.node_outputs,
        "skipped_nodes": ctx.skipped_nodes,
        "approval_context": approval_context or {},
        "nodes": list(ctx.graph.nodes_by_id.values()),
        "edges": _edges_as_dicts(ctx.graph.edges),
    }
    if pause_reason:
        checkpoint["pause_reason"] = pause_reason
    params: dict[str, Any] = {
        _CHECKPOINT_KEY: checkpoint,
        "paused_at_node": paused_at_node,
    }
    if approval_context is not None:
        params["approval_context"] = approval_context
    merge_run_parameters(ctx.client, ctx.run_id, params)
    return checkpoint


def _save_checkpoint(
    ctx: _GraphRunContext,
    *,
    paused_at_node: str,
    batch_index: int,
    approval_context: dict[str, Any],
) -> None:
    _save_graph_checkpoint(
        ctx,
        paused_at_node=paused_at_node,
        batch_index=batch_index,
        approval_context=approval_context,
    )
    update_run(ctx.client, ctx.run_id, status=RUN_STATUS_AWAITING_APPROVAL)


def _execute_graph_node(ctx: _GraphRunContext, node_id: str, step_index: int) -> _NodeRunResult:
    try:
        enforce_interrupt(ctx.client, ctx.org_id, "workflow_run", ctx.run_id, actor_id=ctx.user_id)
    except AgentExecutionInterrupted as exc:
        return _NodeRunResult(node_id, step_index, halt="paused" if exc.signal == "pause" else "cancelled")

    node = ctx.graph.nodes_by_id[node_id]
    policy = _node_policy(node)

    if _is_approval_node(node):
        upstream = _upstream_outputs(ctx.graph, node_id, ctx.node_outputs)
        node_metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
        approval_context = {
            "node_id": node_id,
            "node_name": node.get("name") or node.get("title") or node_id,
            "upstream_outputs": upstream,
            "prompt": node_metadata.get("prompt") or node.get("description") or "Approve to continue",
            "on_reject": policy["on_reject"],
            "reject_route_node_id": policy.get("reject_route_node_id"),
        }
        try:
            from app.workflows.approval_batch_service import create_approval_batch

            batch = create_approval_batch(
                ctx.client,
                org_id=ctx.org_id,
                run_id=ctx.run_id,
                node_id=node_id,
                approval_context=approval_context,
                node_metadata=node_metadata,
            )
            if batch:
                approval_context["batch_id"] = str(batch["id"])
                approval_context["batch_items"] = [
                    {
                        "itemKey": item["item_key"],
                        "label": item["label"],
                        "status": item["status"],
                        "sourceNodeId": item.get("source_node_id"),
                    }
                    for item in (batch.get("items") or [])
                ]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "approval batch creation skipped run_id=%s node_id=%s error=%s",
                ctx.run_id,
                node_id,
                str(exc),
            )
        with ctx.lock:
            ctx.node_outputs[node_id] = {"awaiting_approval": True, "approval_context": approval_context}
        return _NodeRunResult(node_id, step_index, halt="awaiting_approval", error=json.dumps(approval_context))

    step_def = _node_to_step(node, ctx.graph.nodes_by_id, ctx.edge_dicts)
    if step_def is None:
        with ctx.lock:
            ctx.node_outputs[node_id] = {"passthrough": True, "node_type": node.get("node_type")}
        return _NodeRunResult(node_id, step_index + 1)

    step_id = str(step_def["id"])
    step_name = str(step_def.get("name") or step_id)
    step_type = str(step_def["type"])
    config = dict(step_def.get("config") or {})
    if isinstance(step_def.get("metadata"), dict):
        config["metadata"] = step_def["metadata"]

    upstream = _upstream_outputs(ctx.graph, node_id, ctx.node_outputs)
    merged_parameters = {
        **ctx.parameters,
        "upstream_outputs": upstream,
        "skipped_nodes": list(ctx.skipped_nodes),
    }

    created = create_step(
        client=ctx.client,
        run_id=ctx.run_id,
        org_id=ctx.org_id,
        step_id=step_id,
        step_index=step_index,
        step_name=step_name,
        step_type=step_type,
    )
    step_uuid = str(created["id"])
    step_started = datetime.now(timezone.utc).isoformat()
    set_step_running(ctx.client, step_uuid, step_started)

    active_branch = resolve_active_branch(ctx.node_outputs)
    if should_skip_for_branch(config, active_branch):
        skipped_output = {
            "skipped": True,
            "reason": "branch_mismatch",
            "when_branch": config.get("when_branch"),
            "active_branch": active_branch,
            "upstream_outputs": upstream,
        }
        with ctx.lock:
            ctx.node_outputs[node_id] = skipped_output
        update_step(
            client=ctx.client,
            step_uuid=step_uuid,
            status=STEP_STATUS_SKIPPED,
            input_snapshot={"upstream_outputs": upstream},
            output_snapshot=skipped_output,
            logs=_build_execution_log(
                node_id=node_id,
                step_type=step_type,
                upstream=upstream,
                config=config,
                output=skipped_output,
                duration_ms=0,
            ),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        emit_execute_step_completed(ctx.client, ctx.org_id, ctx.user_id, ctx.run_id, step_index, step_id)
        return _NodeRunResult(node_id, step_index + 1)

    attempts = 0
    max_attempts = policy["max_retries"] if policy["on_failure"] == "retry" else 1
    last_exc: Exception | None = None
    while attempts < max_attempts:
        attempts += 1
        try:
            handler = get_handler(step_type)
            if not handler.supports_execute:
                raise ValueError(f"Invalid step type for execute: {step_type}")
            with ctx.lock:
                step_outputs_snapshot = dict(ctx.node_outputs)
            context = StepContext(
                settings=ctx.settings,
                org_id=ctx.org_id,
                user_id=ctx.user_id,
                run_id=ctx.run_id,
                environment_name=ctx.environment_name,
                step_id=step_id,
                step_type=step_type,
                step_index=step_index,
                config=config,
                parameters=merged_parameters,
                step_outputs=step_outputs_snapshot,
                client=ctx.client,
                is_dry_run=False,
            )
            output = handler.execute(context)
            if isinstance(output, dict):
                output = {**output, "upstream_outputs": upstream}
            else:
                output = {"result": output, "upstream_outputs": upstream}
            with ctx.lock:
                ctx.node_outputs[node_id] = output
            completed_at = datetime.now(timezone.utc).isoformat()
            duration_ms = int(
                (datetime.fromisoformat(completed_at) - datetime.fromisoformat(step_started)).total_seconds() * 1000
            )
            update_step(
                client=ctx.client,
                step_uuid=step_uuid,
                status=STEP_STATUS_COMPLETED,
                input_snapshot={"upstream_outputs": upstream, "config": config},
                output_snapshot=output,
                logs=_build_execution_log(
                    node_id=node_id,
                    step_type=step_type,
                    upstream=upstream,
                    config=config,
                    output=output,
                    duration_ms=duration_ms,
                    attempts=attempts,
                ),
                completed_at=completed_at,
            )
            emit_execute_step_completed(ctx.client, ctx.org_id, ctx.user_id, ctx.run_id, step_index, step_id)
            write_audit_event(
                ctx.client,
                ctx.org_id,
                ctx.user_id,
                action="workflow.execute.step_timing",
                resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                resource_id=ctx.run_id,
                metadata={
                    "step_id": step_id,
                    "node_id": node_id,
                    "step_type": step_type,
                    "duration_ms": duration_ms,
                    "execution_mode": "graph",
                    "parallel_batch": True,
                    "attempts": attempts,
                },
            )
            return _NodeRunResult(node_id, step_index + 1)
        except RateLimitError as exc:
            last_exc = exc
            if policy["on_failure"] == "skip":
                break
            if attempts < max_attempts:
                time.sleep(policy["retry_backoff_ms"] / 1000.0)
                continue
            return _handle_node_failure(
                ctx, node_id, step_uuid, step_started, step_index, step_id, step_type, upstream, config,
                ERROR_CODE_RATE_LIMITED, "Rate limit exceeded", exc, rate_limited=True, policy=policy,
            )
        except ValueError as exc:
            last_exc = exc
            if policy["on_failure"] == "skip":
                break
            if attempts < max_attempts:
                time.sleep(policy["retry_backoff_ms"] / 1000.0)
                continue
            return _handle_node_failure(
                ctx, node_id, step_uuid, step_started, step_index, step_id, step_type, upstream, config,
                ERROR_CODE_VALIDATION, str(exc)[:500], exc, policy=policy,
            )
        except Exception as exc:
            last_exc = exc
            if policy["on_failure"] == "skip":
                break
            if attempts < max_attempts:
                time.sleep(policy["retry_backoff_ms"] / 1000.0)
                continue
            from app.services.canvas_write_gate import (
                CANVAS_WRITE_AUTHORITY_BLOCKED,
                user_facing_message_from_write_authority_error,
            )

            write_gate_msg = user_facing_message_from_write_authority_error(exc)
            if write_gate_msg:
                code, message = CANVAS_WRITE_AUTHORITY_BLOCKED, write_gate_msg
            else:
                code = ERROR_CODE_STEP_FAILED
                message = "Step execution failed"
                if "rag" in step_type.lower():
                    code, message = ERROR_CODE_RAG_UNAVAILABLE, "Retrieval temporarily unavailable"
                elif "slack" in step_type.lower():
                    code, message = ERROR_CODE_SLACK_FAILED, "Slack send failed"
                elif "email" in step_type.lower():
                    code, message = ERROR_CODE_EMAIL_FAILED, "Email send failed"
                elif "webhook" in step_type.lower():
                    code, message = ERROR_CODE_WEBHOOK_FAILED, "Webhook send failed"
            return _handle_node_failure(
                ctx, node_id, step_uuid, step_started, step_index, step_id, step_type, upstream, config,
                code, message, exc, policy=policy,
            )

    if policy["on_failure"] == "skip":
        skipped_output = {
            "skipped": True,
            "reason": "on_failure_skip",
            "error": str(last_exc) if last_exc else "unknown",
            "upstream_outputs": upstream,
        }
        with ctx.lock:
            ctx.node_outputs[node_id] = skipped_output
            ctx.skipped_nodes.append(node_id)
        update_step(
            client=ctx.client,
            step_uuid=step_uuid,
            status=STEP_STATUS_SKIPPED,
            input_snapshot={"upstream_outputs": upstream},
            output_snapshot=skipped_output,
            logs=_build_execution_log(
                node_id=node_id,
                step_type=step_type,
                upstream=upstream,
                config=config,
                output=skipped_output,
                duration_ms=0,
                error_message=str(last_exc) if last_exc else None,
                attempts=attempts,
            ),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        emit_execute_step_completed(ctx.client, ctx.org_id, ctx.user_id, ctx.run_id, step_index, step_id)
        return _NodeRunResult(node_id, step_index + 1)

    return _NodeRunResult(node_id, step_index, halt="failed", error=str(last_exc) if last_exc else "Step failed")


def _handle_node_failure(
    ctx: _GraphRunContext,
    node_id: str,
    step_uuid: str,
    step_started: str,
    step_index: int,
    step_id: str,
    step_type: str,
    upstream: dict[str, Any],
    config: dict[str, Any],
    code: str,
    message: str,
    exc: Exception,
    *,
    rate_limited: bool = False,
    policy: dict[str, Any],
) -> _NodeRunResult:
    if policy["on_failure"] == "skip":
        skipped_output = {"skipped": True, "reason": "on_failure_skip", "error": message, "upstream_outputs": upstream}
        with ctx.lock:
            ctx.skipped_nodes.append(node_id)
            ctx.node_outputs[node_id] = skipped_output
        update_step(
            client=ctx.client,
            step_uuid=step_uuid,
            status=STEP_STATUS_SKIPPED,
            input_snapshot={"upstream_outputs": upstream},
            output_snapshot=skipped_output,
            logs=_build_execution_log(
                node_id=node_id,
                step_type=step_type,
                upstream=upstream,
                config=config,
                output=skipped_output,
                duration_ms=0,
                error_code=code,
                error_message=message,
            ),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        emit_execute_step_completed(ctx.client, ctx.org_id, ctx.user_id, ctx.run_id, step_index, step_id)
        return _NodeRunResult(node_id, step_index + 1)

    duration_ms = int(
        (datetime.now(timezone.utc) - datetime.fromisoformat(step_started)).total_seconds() * 1000
    )
    update_step(
        client=ctx.client,
        step_uuid=step_uuid,
        status=STEP_STATUS_FAILED,
        input_snapshot={"upstream_outputs": upstream},
        error_code=code,
        error_message=message,
        is_retryable=code == ERROR_CODE_RAG_UNAVAILABLE,
        logs=_build_execution_log(
            node_id=node_id,
            step_type=step_type,
            upstream=upstream,
            config=config,
            output=None,
            duration_ms=duration_ms,
            error_code=code,
            error_message=message,
        ),
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    emit_execute_step_failed(ctx.client, ctx.org_id, ctx.user_id, ctx.run_id, step_index, step_id, code)
    write_audit_event(
        ctx.client,
        ctx.org_id,
        ctx.user_id,
        action="workflow.execute.step_timing",
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=ctx.run_id,
        metadata={
            "step_id": step_id,
            "node_id": node_id,
            "step_type": step_type,
            "duration_ms": duration_ms,
            "execution_mode": "graph",
            "error_code": code,
        },
    )
    result = _NodeRunResult(node_id, step_index, halt="failed", error=str(exc))
    result.rate_limited = rate_limited
    return result


def _batch_requires_serial(ctx: _GraphRunContext, batch: list[str]) -> bool:
    if len(batch) <= 1:
        return True
    return any(_is_approval_node(ctx.graph.nodes_by_id[nid]) for nid in batch)


def _batch_index_for_node(batches: list[list[str]], node_id: str) -> int:
    for idx, batch in enumerate(batches):
        if node_id in batch:
            return idx
    raise GraphValidationError(f"Node {node_id} not found in execution graph")


def _downstream_node_ids(graph: ExecutionGraph, node_id: str) -> set[str]:
    from collections import deque

    seen: set[str] = set()
    queue: deque[str] = deque(graph.successors.get(node_id, []))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(graph.successors.get(current, []))
    return seen


def _node_outputs_from_completed_steps(steps: list[dict[str, Any]]) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for step in steps:
        status = str(step.get("status") or "")
        if status not in {STEP_STATUS_COMPLETED, STEP_STATUS_SKIPPED}:
            continue
        node_id = str(step.get("step_id") or "")
        snapshot = step.get("output_snapshot")
        if node_id and isinstance(snapshot, dict):
            outputs[node_id] = snapshot
    return outputs


def _graph_from_run(run: dict[str, Any]) -> tuple[ExecutionGraph, list[list[str]]]:
    definition = run.get("definition_snapshot") or {}
    graph_payload = definition.get("graph") if isinstance(definition.get("graph"), dict) else {}
    nodes = graph_payload.get("nodes") or definition.get("nodes") or []
    edges = graph_payload.get("edges") or definition.get("edges") or []
    graph = build_execution_graph(nodes, edges)
    validate_execution_graph(graph)
    return graph, topological_batches(graph)


def _run_graph_batches(
    ctx: _GraphRunContext,
    batches: list[list[str]],
    *,
    start_batch: int = 0,
    skip_nodes_with_outputs: bool = False,
) -> tuple[str, list[str], bool]:
    errors: list[str] = []
    rate_limited = False

    for batch_idx, batch in enumerate(batches[start_batch:], start=start_batch):
        node_ids = batch
        if skip_nodes_with_outputs:
            node_ids = [node_id for node_id in batch if node_id not in ctx.node_outputs]
        if not node_ids:
            continue

        base_index = ctx.step_index
        if _batch_requires_serial(ctx, node_ids):
            outcomes = [
                _execute_graph_node(ctx, node_id, base_index + offset)
                for offset, node_id in enumerate(node_ids)
            ]
        else:
            outcomes = []
            with ThreadPoolExecutor(max_workers=min(len(node_ids), 8)) as pool:
                futures = {
                    pool.submit(_execute_graph_node, ctx, node_id, base_index + offset): node_id
                    for offset, node_id in enumerate(node_ids)
                }
                by_node = {}
                for future in as_completed(futures):
                    by_node[futures[future]] = future.result()
                outcomes = [by_node[nid] for nid in node_ids]

        ctx.step_index = max((o.step_index for o in outcomes), default=ctx.step_index)

        for outcome in outcomes:
            if outcome.rate_limited:
                rate_limited = True
            if outcome.halt == "awaiting_approval":
                approval_context = json.loads(outcome.error or "{}")
                _save_checkpoint(ctx, paused_at_node=outcome.node_id, batch_index=batch_idx, approval_context=approval_context)
                return RUN_STATUS_AWAITING_APPROVAL, errors, rate_limited
            if outcome.halt == "paused":
                _save_graph_checkpoint(
                    ctx,
                    paused_at_node=outcome.node_id,
                    batch_index=batch_idx,
                    pause_reason="operator_interrupt",
                )
                update_run(ctx.client, ctx.run_id, status=RUN_STATUS_PAUSED)
                return RUN_STATUS_PAUSED, errors, rate_limited
            if outcome.halt == "cancelled":
                errors.append("Interrupted by operator")
                return RUN_STATUS_CANCELLED, errors, rate_limited
            if outcome.halt == "failed":
                errors.append(outcome.error or "Step failed")
                return RUN_STATUS_FAILED, errors, rate_limited

    return RUN_STATUS_COMPLETED, errors, rate_limited


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
    del steps_exist  # reserved for resume/idempotency
    graph = build_execution_graph(nodes, edges)
    validate_execution_graph(graph)
    batches = topological_batches(graph)

    ctx = _GraphRunContext(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        graph=graph,
        edge_dicts=_edges_as_dicts(graph.edges),
        parameters=dict(parameters or {}),
        client=client,
        environment_name=environment_name,
        node_outputs={},
        skipped_nodes=[],
    )

    final_status, errors, rate_limited = _run_graph_batches(ctx, batches)
    run_error_message = errors[0] if errors else None
    return _finalize_run(ctx, final_status=final_status, errors=errors, run_error_message=run_error_message, rate_limited=rate_limited)


def _resume_graph_from_node(
    ctx: _GraphRunContext,
    batches: list[list[str]],
    *,
    start_node_id: str,
    batch_index: int,
    node_output_patch: dict[str, Any] | None = None,
    parameter_patch: dict[str, Any] | None = None,
) -> tuple[str, list[dict], list[str], bool]:
    downstream = _downstream_node_ids(ctx.graph, start_node_id)
    for downstream_id in downstream:
        ctx.node_outputs.pop(downstream_id, None)
    ctx.node_outputs.pop(start_node_id, None)
    if node_output_patch:
        ctx.node_outputs.update(node_output_patch)
    if parameter_patch:
        ctx.parameters.update(parameter_patch)
    merge_run_parameters(
        ctx.client,
        ctx.run_id,
        {_CHECKPOINT_KEY: None, "paused_at_node": None, "approval_context": None, **(parameter_patch or {})},
    )
    update_run(ctx.client, ctx.run_id, status="running")
    final_status, errors, rate_limited = _run_graph_batches(
        ctx,
        batches,
        start_batch=batch_index,
        skip_nodes_with_outputs=True,
    )
    run_error_message = errors[0] if errors else None
    return _finalize_run(
        ctx,
        final_status=final_status,
        errors=errors,
        run_error_message=run_error_message,
        rate_limited=rate_limited,
    )


def _route_upstream_on_reject(
    ctx: _GraphRunContext,
    batches: list[list[str]],
    *,
    batch_index: int,
    paused_at: str,
    approval_context: dict[str, Any],
    comment: str | None,
) -> tuple[str, list[dict], list[str], bool]:
    route_node = approval_context.get("reject_route_node_id")
    if not route_node:
        return _finalize_run(
            ctx,
            final_status=RUN_STATUS_FAILED,
            errors=["Approval rejected; missing reject_route_node_id for route_upstream"],
            run_error_message="Approval rejected",
            rate_limited=False,
        )
    route_node = str(route_node)
    ctx.node_outputs[str(paused_at)] = {
        "approved": False,
        "decision": "rejected",
        "comment": comment,
        "approval_context": approval_context,
        "route_upstream": route_node,
    }
    start_batch = _batch_index_for_node(batches, route_node)
    return _resume_graph_from_node(
        ctx,
        batches,
        start_node_id=route_node,
        batch_index=start_batch,
    )


def resolve_approval_batch_and_resume(
    settings: Settings,
    org_id: str,
    user_id: str,
    run_id: str,
    *,
    batch_id: str,
    client: Any,
    environment_name: str = "default",
) -> tuple[str, list[dict], list[str], bool]:
    """Resolve a batch approval gate after per-item decisions (STA-290)."""
    from app.workflows.approval_batch_service import (
        get_active_batch_for_run,
        summarize_batch_items,
    )

    batch = get_active_batch_for_run(client, org_id, run_id)
    if not batch or str(batch["id"]) != str(batch_id):
        raise GraphValidationError("Approval batch not found for run")
    summary = summarize_batch_items(batch.get("items") or [])
    if summary["pending"]:
        raise GraphValidationError("All batch items must be decided before resume")

    if summary["all_approved"]:
        return resume_workflow_graph(
            settings,
            org_id,
            user_id,
            run_id,
            decision="approved",
            client=client,
            environment_name=environment_name,
        )
    if summary["all_rejected"]:
        return resume_workflow_graph(
            settings,
            org_id,
            user_id,
            run_id,
            decision="rejected",
            client=client,
            environment_name=environment_name,
        )

    run = get_run_with_steps(client, org_id, run_id, environment_name)
    if not run:
        raise GraphValidationError("Run not found")
    params = dict(run.get("parameters") or {})
    checkpoint = params.get(_CHECKPOINT_KEY) or {}
    paused_at = checkpoint.get("paused_at_node") or params.get("paused_at_node")
    if not paused_at:
        raise GraphValidationError("Missing paused_at_node checkpoint")

    nodes = checkpoint.get("nodes") or (run.get("definition_snapshot") or {}).get("graph", {}).get("nodes") or []
    edges = checkpoint.get("edges") or (run.get("definition_snapshot") or {}).get("graph", {}).get("edges") or []
    graph = build_execution_graph(nodes, edges)
    batches = topological_batches(graph)
    batch_index = int(checkpoint.get("batch_index") or 0)
    approval_context = dict(checkpoint.get("approval_context") or params.get("approval_context") or {})
    on_reject = str(approval_context.get("on_reject") or "fail_workflow")

    rejected = summary["rejected"]
    route_candidates = [
        str(item.get("route_to_node_id") or item.get("source_node_id") or "")
        for item in rejected
        if item.get("route_to_node_id") or item.get("source_node_id")
    ]
    route_node = next((node_id for node_id in route_candidates if node_id in graph.nodes_by_id), None)
    if not route_node and on_reject != "route_upstream":
        raise GraphValidationError("Partial rejection requires route_to_node_id on rejected items or route_upstream policy")
    if not route_node:
        route_node = approval_context.get("reject_route_node_id")
    if not route_node or str(route_node) not in graph.nodes_by_id:
        raise GraphValidationError("Partial rejection missing valid upstream route node")

    approved_items = [
        {
            "itemKey": item["item_key"],
            "label": item["label"],
            "sourceNodeId": item.get("source_node_id"),
            "payload": item.get("payload") or {},
        }
        for item in summary["approved"]
    ]
    ctx = _GraphRunContext(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        graph=graph,
        edge_dicts=_edges_as_dicts(graph.edges),
        parameters=params,
        client=client,
        environment_name=environment_name,
        node_outputs=dict(checkpoint.get("node_outputs") or {}),
        skipped_nodes=list(checkpoint.get("skipped_nodes") or []),
        step_index=int(checkpoint.get("step_index") or 0),
    )
    ctx.node_outputs[str(paused_at)] = {
        "approved": False,
        "decision": "partial",
        "approval_context": approval_context,
        "batch_id": batch_id,
        "approved_items": approved_items,
        "rejected_items": [
            {
                "itemKey": item["item_key"],
                "label": item["label"],
                "sourceNodeId": item.get("source_node_id"),
                "rejectComment": item.get("reject_comment"),
            }
            for item in rejected
        ],
    }
    client.table("approval_batches").update({"status": "resolved", "updated_at": datetime.now(timezone.utc).isoformat()}).eq(
        "id", batch_id
    ).execute()
    start_batch = _batch_index_for_node(batches, str(route_node))
    return _resume_graph_from_node(
        ctx,
        batches,
        start_node_id=str(route_node),
        batch_index=start_batch,
        parameter_patch={"batch_approved_items": approved_items},
    )


def resume_workflow_graph(
    settings: Settings,
    org_id: str,
    user_id: str,
    run_id: str,
    *,
    decision: str,
    client: Any,
    environment_name: str = "default",
    comment: str | None = None,
) -> tuple[str, list[dict], list[str], bool]:
    """Resume a graph run paused at an approval node (STA-139)."""
    run = get_run_with_steps(client, org_id, run_id, environment_name)
    if not run:
        raise GraphValidationError("Run not found")
    if run.get("status") != RUN_STATUS_AWAITING_APPROVAL:
        raise GraphValidationError(f"Run is not awaiting approval (status={run.get('status')})")

    params = dict(run.get("parameters") or {})
    checkpoint = params.get(_CHECKPOINT_KEY) or {}
    paused_at = checkpoint.get("paused_at_node") or params.get("paused_at_node")
    if not paused_at:
        raise GraphValidationError("Missing paused_at_node checkpoint")

    nodes = checkpoint.get("nodes") or (run.get("definition_snapshot") or {}).get("graph", {}).get("nodes") or []
    edges = checkpoint.get("edges") or (run.get("definition_snapshot") or {}).get("graph", {}).get("edges") or []
    graph = build_execution_graph(nodes, edges)
    batches = topological_batches(graph)
    batch_index = int(checkpoint.get("batch_index") or 0)

    approval_context = dict(checkpoint.get("approval_context") or params.get("approval_context") or {})
    on_reject = str(approval_context.get("on_reject") or "fail_workflow")
    normalized = str(decision or "").lower()

    ctx = _GraphRunContext(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        graph=graph,
        edge_dicts=_edges_as_dicts(graph.edges),
        parameters=params,
        client=client,
        environment_name=environment_name,
        node_outputs=dict(checkpoint.get("node_outputs") or {}),
        skipped_nodes=list(checkpoint.get("skipped_nodes") or []),
        step_index=int(checkpoint.get("step_index") or 0),
    )

    if normalized == "rejected":
        ctx.node_outputs[str(paused_at)] = {
            "approved": False,
            "decision": "rejected",
            "comment": comment,
            "approval_context": approval_context,
        }
        if on_reject == "skip":
            ctx.skipped_nodes.append(str(paused_at))
            merge_run_parameters(client, run_id, {_CHECKPOINT_KEY: None, "paused_at_node": None})
            update_run(client, run_id, status="running")
            final_status, errors, rate_limited = _run_graph_batches(ctx, batches, start_batch=batch_index + 1)
            return _finalize_run(ctx, final_status=final_status, errors=errors, run_error_message=errors[0] if errors else None, rate_limited=rate_limited)
        if on_reject == "route_upstream":
            return _route_upstream_on_reject(
                ctx,
                batches,
                batch_index=batch_index,
                paused_at=str(paused_at),
                approval_context=approval_context,
                comment=comment,
            )
        return _finalize_run(
            ctx,
            final_status=RUN_STATUS_FAILED,
            errors=["Approval rejected"],
            run_error_message="Approval rejected",
            rate_limited=False,
        )

    if normalized != "approved":
        raise GraphValidationError("decision must be approved or rejected")

    batch_id = approval_context.get("batch_id")
    if batch_id:
        client.table("approval_batches").update(
            {"status": "resolved", "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", str(batch_id)).execute()

    ctx.node_outputs[str(paused_at)] = {
        "approved": True,
        "decision": "approved",
        "comment": comment,
        "approval_context": approval_context,
    }
    merge_run_parameters(client, run_id, {_CHECKPOINT_KEY: None, "paused_at_node": None, "approval_context": None})
    update_run(client, run_id, status="running")

    final_status, errors, rate_limited = _run_graph_batches(
        ctx,
        batches,
        start_batch=batch_index + 1,
    )
    run_error_message = errors[0] if errors else None
    return _finalize_run(ctx, final_status=final_status, errors=errors, run_error_message=run_error_message, rate_limited=rate_limited)


def resume_paused_workflow_graph(
    settings: Settings,
    org_id: str,
    user_id: str,
    run_id: str,
    *,
    client: Any,
    environment_name: str = "default",
) -> tuple[str, list[dict], list[str], bool]:
    """Resume a graph run paused by operator interrupt (STA-170)."""
    run = get_run_with_steps(client, org_id, run_id, environment_name)
    if not run:
        raise GraphValidationError("Run not found")
    if run.get("status") != RUN_STATUS_PAUSED:
        raise GraphValidationError(f"Run is not paused (status={run.get('status')})")

    params = dict(run.get("parameters") or {})
    checkpoint = params.get(_CHECKPOINT_KEY) or {}
    if not checkpoint:
        raise GraphValidationError("Missing pause checkpoint — cannot resume this run")

    graph, batches = _graph_from_run(run)
    batch_index = int(checkpoint.get("batch_index") or 0)
    ctx = _GraphRunContext(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        graph=graph,
        edge_dicts=_edges_as_dicts(graph.edges),
        parameters=params,
        client=client,
        environment_name=environment_name,
        node_outputs=dict(checkpoint.get("node_outputs") or {}),
        skipped_nodes=list(checkpoint.get("skipped_nodes") or []),
        step_index=int(checkpoint.get("step_index") or 0),
    )
    merge_run_parameters(
        client,
        run_id,
        {_CHECKPOINT_KEY: None, "paused_at_node": None, "approval_context": None},
    )
    update_run(client, run_id, status="running", error_message=None)
    final_status, errors, rate_limited = _run_graph_batches(
        ctx,
        batches,
        start_batch=batch_index,
        skip_nodes_with_outputs=True,
    )
    run_error_message = errors[0] if errors else None
    return _finalize_run(
        ctx,
        final_status=final_status,
        errors=errors,
        run_error_message=run_error_message,
        rate_limited=rate_limited,
    )


def retry_workflow_step(
    settings: Settings,
    org_id: str,
    user_id: str,
    run_id: str,
    step_uuid: str,
    *,
    client: Any,
    environment_name: str = "default",
) -> tuple[str, list[dict], list[str], bool]:
    """Re-run a failed workflow step and its downstream nodes."""
    run = get_run_with_steps(client, org_id, run_id, environment_name)
    if not run:
        raise GraphValidationError("Run not found")
    if str(run.get("status") or "") not in {RUN_STATUS_FAILED, RUN_STATUS_PAUSED}:
        raise GraphValidationError(f"Run cannot retry step in status={run.get('status')}")

    steps = list(run.get("steps") or [])
    target = next((step for step in steps if str(step.get("id")) == str(step_uuid)), None)
    if not target:
        raise GraphValidationError("Step not found")
    if str(target.get("status") or "") != STEP_STATUS_FAILED and not target.get("is_retryable"):
        raise GraphValidationError("Step is not retryable")

    node_id = str(target.get("step_id") or "")
    if not node_id:
        raise GraphValidationError("Step is missing node reference")

    graph, batches = _graph_from_run(run)
    batch_index = _batch_index_for_node(batches, node_id)
    step_index = int(target.get("step_index") or 0)
    prior_steps = [step for step in steps if int(step.get("step_index") or 0) < step_index]
    node_outputs = _node_outputs_from_completed_steps(prior_steps)
    downstream = _downstream_node_ids(graph, node_id)
    for downstream_id in downstream:
        node_outputs.pop(downstream_id, None)
    node_outputs.pop(node_id, None)

    client.table("workflow_steps").delete().eq("run_id", run_id).gte("step_index", step_index).execute()

    params = dict(run.get("parameters") or {})
    ctx = _GraphRunContext(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        graph=graph,
        edge_dicts=_edges_as_dicts(graph.edges),
        parameters=params,
        client=client,
        environment_name=environment_name,
        node_outputs=node_outputs,
        skipped_nodes=[],
        step_index=step_index,
    )
    merge_run_parameters(
        client,
        run_id,
        {_CHECKPOINT_KEY: None, "paused_at_node": None, "approval_context": None},
    )
    update_run(client, run_id, status="running", error_message=None)
    final_status, errors, rate_limited = _run_graph_batches(
        ctx,
        batches,
        start_batch=batch_index,
        skip_nodes_with_outputs=True,
    )
    run_error_message = errors[0] if errors else None
    return _finalize_run(
        ctx,
        final_status=final_status,
        errors=errors,
        run_error_message=run_error_message,
        rate_limited=rate_limited,
    )
