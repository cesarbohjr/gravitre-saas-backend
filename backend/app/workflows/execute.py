"""BE-20: Constrained execute engine. rag_retrieve, noop, slack_post_message (IN-10), email_send (IN-11)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.core.logging import get_logger, request_id_ctx
from app.connectors.rate_limit import RateLimitError
from app.workflows import handlers as _handlers
from app.workflows.registry import StepContext, get_handler
from app.workflows.audit import write_audit_event
from app.services.council_workflow_service import resolve_active_branch, should_skip_for_branch
from app.services.agent_interrupt_service import AgentExecutionInterrupted, enforce_interrupt
from app.workflows.constants import (
    ERROR_CODE_EMAIL_FAILED,
    ERROR_CODE_RAG_UNAVAILABLE,
    ERROR_CODE_RATE_LIMITED,
    ERROR_CODE_SLACK_FAILED,
    ERROR_CODE_STEP_FAILED,
    ERROR_CODE_WEBHOOK_FAILED,
    ERROR_CODE_VALIDATION,
    RESOURCE_TYPE_WORKFLOW_RUN,
    RUN_STATUS_CANCELLED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_PAUSED,
    STEP_STATUS_COMPLETED,
    STEP_STATUS_FAILED,
    STEP_STATUS_SKIPPED,
)
from app.workflows.repository import (
    create_step,
    emit_execute_completed,
    emit_execute_failed,
    emit_execute_started,
    emit_execute_step_completed,
    emit_execute_step_failed,
    get_run_with_steps,
    set_step_running,
    update_run,
    update_step,
)

logger = get_logger(__name__)


def execute_workflow_steps(
    settings: Settings,
    org_id: str,
    user_id: str,
    run_id: str,
    definition: dict[str, Any],
    parameters: dict[str, Any],
    client: Any,
    environment_name: str = "default",
    steps_exist: bool = False,
) -> tuple[str, list[dict], list[str], bool]:
    """
    Execute steps for an approved run. Only rag_retrieve and noop.
    If steps_exist=True, use existing step records (noop approval flow).
    Returns (final_status, step_rows, errors).
    """
    steps_def = definition.get("steps", [])
    graph_block = definition.get("graph")
    if isinstance(graph_block, dict):
        graph_nodes = graph_block.get("nodes")
        graph_edges = graph_block.get("edges")
        if isinstance(graph_nodes, list) and graph_nodes and isinstance(graph_edges, list):
            from app.workflows.execution_engine import execute_workflow_graph

            return execute_workflow_graph(
                settings,
                org_id,
                user_id,
                run_id,
                graph_nodes,
                graph_edges,
                parameters,
                client,
                environment_name,
                steps_exist,
            )

    step_outputs: dict[str, Any] = {}
    errors: list[str] = []
    run_failed = False
    run_paused = False
    run_cancelled = False
    run_error_message: str | None = None
    rate_limited = False
    existing_steps: list[dict] = []
    if steps_exist:
        run_with = get_run_with_steps(client, org_id, run_id, environment_name)
        existing_steps = (run_with or {}).get("steps", [])

    for idx, sdef in enumerate(steps_def):
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

        step_id = sdef["id"]
        step_name = sdef["name"]
        step_type = sdef["type"]
        config = dict(sdef.get("config") or {})
        if isinstance(sdef.get("metadata"), dict):
            config["metadata"] = sdef["metadata"]
        if steps_exist and idx < len(existing_steps):
            step_uuid = str(existing_steps[idx]["id"])
        else:
            created = create_step(
                client=client,
                run_id=run_id,
                org_id=org_id,
                step_id=step_id,
                step_index=idx,
                step_name=step_name,
                step_type=step_type,
            )
            step_uuid = str(created["id"])
        step_started = datetime.now(timezone.utc).isoformat()
        set_step_running(client, step_uuid, step_started)

        active_branch = resolve_active_branch(step_outputs)
        if should_skip_for_branch(config, active_branch):
            skipped_output = {
                "skipped": True,
                "reason": "branch_mismatch",
                "when_branch": config.get("when_branch"),
                "active_branch": active_branch,
            }
            step_outputs[step_id] = skipped_output
            update_step(
                client=client,
                step_uuid=step_uuid,
                status=STEP_STATUS_SKIPPED,
                output_snapshot=skipped_output,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            emit_execute_step_completed(client, org_id, user_id, run_id, idx, step_id)
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
                step_index=idx,
                config=config,
                parameters=parameters,
                step_outputs=step_outputs,
                client=client,
                is_dry_run=False,
            )
            output = handler.execute(context)
            step_outputs[step_id] = output
            completed_at = datetime.now(timezone.utc).isoformat()
            duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(step_started)).total_seconds() * 1000)
            update_step(
                client=client,
                step_uuid=step_uuid,
                status=STEP_STATUS_COMPLETED,
                output_snapshot=output,
                completed_at=completed_at,
            )
            emit_execute_step_completed(client, org_id, user_id, run_id, idx, step_id)
            write_audit_event(
                client, org_id, user_id,
                action="workflow.execute.step_timing",
                resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                resource_id=run_id,
                metadata={
                    "step_id": step_id,
                    "step_type": step_type,
                    "duration_ms": duration_ms,
                },
            )
            logger.info(
                "workflow_step_completed request_id=%s org_id=%s run_id=%s step_id=%s step_type=%s duration_ms=%s",
                request_id_ctx.get(),
                org_id,
                run_id,
                step_id,
                step_type,
                duration_ms,
            )
        except RateLimitError as e:
            rate_limited = True
            run_failed = True
            run_error_message = "Rate limit exceeded"
            duration_ms = int((datetime.now(timezone.utc) - datetime.fromisoformat(step_started)).total_seconds() * 1000)
            update_step(
                client=client,
                step_uuid=step_uuid,
                status=STEP_STATUS_FAILED,
                error_code=ERROR_CODE_RATE_LIMITED,
                error_message=run_error_message,
                is_retryable=True,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            emit_execute_step_failed(client, org_id, user_id, run_id, idx, step_id, ERROR_CODE_RATE_LIMITED)
            write_audit_event(
                client, org_id, user_id,
                action="workflow.execute.step_timing",
                resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                resource_id=run_id,
                metadata={
                    "step_id": step_id,
                    "step_type": step_type,
                    "duration_ms": duration_ms,
                },
            )
            logger.info(
                "workflow_step_failed request_id=%s org_id=%s run_id=%s step_id=%s step_type=%s duration_ms=%s error=rate_limited",
                request_id_ctx.get(),
                org_id,
                run_id,
                step_id,
                step_type,
                duration_ms,
            )
            errors.append(str(e))
            break
        except ValueError as e:
            run_failed = True
            run_error_message = "Step validation failed"
            duration_ms = int((datetime.now(timezone.utc) - datetime.fromisoformat(step_started)).total_seconds() * 1000)
            err_msg = str(e)
            update_step(
                client=client,
                step_uuid=step_uuid,
                status=STEP_STATUS_FAILED,
                error_code=ERROR_CODE_VALIDATION,
                error_message=err_msg[:500],
                is_retryable=False,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            emit_execute_step_failed(client, org_id, user_id, run_id, idx, step_id, ERROR_CODE_VALIDATION)
            write_audit_event(
                client, org_id, user_id,
                action="workflow.execute.step_timing",
                resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                resource_id=run_id,
                metadata={
                    "step_id": step_id,
                    "step_type": step_type,
                    "duration_ms": duration_ms,
                },
            )
            logger.info(
                "workflow_step_failed request_id=%s org_id=%s run_id=%s step_id=%s step_type=%s duration_ms=%s error=validation",
                request_id_ctx.get(),
                org_id,
                run_id,
                step_id,
                step_type,
                duration_ms,
            )
            errors.append(err_msg)
            break
        except Exception:
            run_failed = True
            duration_ms = int((datetime.now(timezone.utc) - datetime.fromisoformat(step_started)).total_seconds() * 1000)
            is_rag = "rag" in step_type.lower()
            is_slack = "slack" in step_type.lower()
            is_email = "email" in step_type.lower()
            is_webhook = "webhook" in step_type.lower()
            if is_rag:
                run_error_message = "Retrieval temporarily unavailable"
                code = ERROR_CODE_RAG_UNAVAILABLE
            elif is_slack:
                run_error_message = "Slack send failed"
                code = ERROR_CODE_SLACK_FAILED
            elif is_email:
                run_error_message = "Email send failed"
                code = ERROR_CODE_EMAIL_FAILED
            elif is_webhook:
                run_error_message = "Webhook send failed"
                code = ERROR_CODE_WEBHOOK_FAILED
            else:
                run_error_message = "Step execution failed"
                code = ERROR_CODE_STEP_FAILED
            update_step(
                client=client,
                step_uuid=step_uuid,
                status=STEP_STATUS_FAILED,
                error_code=code,
                error_message=run_error_message,
                is_retryable=is_rag,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            emit_execute_step_failed(client, org_id, user_id, run_id, idx, step_id, code)
            write_audit_event(
                client, org_id, user_id,
                action="workflow.execute.step_timing",
                resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                resource_id=run_id,
                metadata={
                    "step_id": step_id,
                    "step_type": step_type,
                    "duration_ms": duration_ms,
                },
            )
            logger.info(
                "workflow_step_failed request_id=%s org_id=%s run_id=%s step_id=%s step_type=%s duration_ms=%s error=step_failed",
                request_id_ctx.get(),
                org_id,
                run_id,
                step_id,
                step_type,
                duration_ms,
            )
            errors.append(run_error_message)
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
        try:
            from app.services.compensation_service import compensate_failed_autonomous_run

            compensate_failed_autonomous_run(
                client,
                settings,
                org_id=org_id,
                run_id=run_id,
                actor_id=user_id,
                parameters=parameters,
                environment_name=environment_name,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "workflow compensation skipped org_id=%s run_id=%s error=%s",
                org_id,
                run_id,
                str(exc),
            )
    else:
        emit_execute_completed(client, org_id, user_id, run_id, final_status)
    try:
        from app.marketplace.adoption import maybe_record_workflow_adoption

        maybe_record_workflow_adoption(
            client,
            org_id=org_id,
            run_id=run_id,
            final_status=final_status,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "marketplace adoption hook skipped org_id=%s run_id=%s error=%s",
            org_id,
            run_id,
            str(exc),
        )
    transparency_log_id = parameters.get("_transparency_log_id")
    if transparency_log_id:
        try:
            from app.services.transparency_service import finalize_decision_log_from_run

            finalize_decision_log_from_run(
                client,
                org_id=org_id,
                log_id=str(transparency_log_id),
                workflow_run_id=run_id,
                final_status=final_status,
                errors=errors,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "transparency log finalize skipped org_id=%s run_id=%s error=%s",
                org_id,
                run_id,
                str(exc),
            )
    return final_status, step_rows, errors, rate_limited
