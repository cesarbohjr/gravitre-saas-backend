"""BE-11: Dry-run execution engine. Deterministic; RAG = real read, others simulated."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.workflows.constants import (
    ERROR_CODE_RAG_UNAVAILABLE,
    ERROR_CODE_STEP_FAILED,
    ERROR_CODE_VALIDATION,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    SCHEMA_VERSION,
    STEP_STATUS_COMPLETED,
    STEP_STATUS_FAILED,
    STEP_STATUS_RUNNING,
)
from app.workflows import handlers as _handlers
from app.workflows.registry import StepContext, get_handler
from app.workflows.repository import (
    create_run,
    create_step,
    emit_dry_run_completed,
    emit_dry_run_started,
    emit_dry_run_step_completed,
    emit_dry_run_step_failed,
    get_run_with_steps,
    get_supabase_client,
    set_step_running,
    update_run,
    update_step,
)
from app.workflows.schema import (
    WorkflowValidationError,
    compute_run_hash,
    validate_definition,
    validate_parameters,
)




def execute_dry_run(
    settings: Settings,
    org_id: str,
    user_id: str,
    definition: dict[str, Any],
    parameters: dict[str, Any] | None,
    workflow_id: str | None = None,
    environment_name: str = "default",
    workflow_version_id: str | None = None,
) -> tuple[str, str, list[dict], list[dict], list[str]]:
    """
    Validate, create run + steps, execute steps. Returns (run_id, status, steps, plan, errors).
    Raises WorkflowValidationError on validation failure.
    On RAG failure: run and steps are persisted; returns status=failed, errors list; caller may raise 503.
    """
    definition = validate_definition(definition)
    parameters = validate_parameters(parameters)
    run_hash = compute_run_hash(definition, parameters, definition.get("schema_version", SCHEMA_VERSION))
    client = get_supabase_client(settings)
    run = create_run(
        client=client,
        org_id=org_id,
        triggered_by=user_id,
        definition_snapshot=definition,
        parameters=parameters,
        run_hash=run_hash,
        workflow_id=workflow_id,
        environment_name=environment_name,
        workflow_version_id=workflow_version_id,
    )
    run_id = str(run["id"])
    emit_dry_run_started(client, org_id, user_id, run_id)

    steps_def = definition.get("steps", [])
    plan = [{"step_id": s["id"], "step_name": s["name"]} for s in steps_def]
    step_outputs: dict[str, Any] = {}
    errors: list[str] = []
    run_failed = False
    run_error_message: str | None = None
    now_iso = datetime.now(timezone.utc).isoformat()

    for idx, sdef in enumerate(steps_def):
        step_id = sdef["id"]
        step_name = sdef["name"]
        step_type = sdef["type"]
        config = sdef.get("config") or {}
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
        set_step_running(client, step_uuid, now_iso)

        try:
            handler = get_handler(step_type)
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
                is_dry_run=True,
            )
            output = handler.simulate(context)
            step_outputs[step_id] = output
            completed_at = datetime.now(timezone.utc).isoformat()
            update_step(
                client=client,
                step_uuid=step_uuid,
                status=STEP_STATUS_COMPLETED,
                output_snapshot=output,
                completed_at=completed_at,
            )
            emit_dry_run_step_completed(client, org_id, user_id, run_id, idx, step_id)
        except ValueError as e:
            run_failed = True
            run_error_message = "Step validation failed"
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
            emit_dry_run_step_failed(client, org_id, user_id, run_id, idx, step_id, ERROR_CODE_VALIDATION)
            errors.append(err_msg)
            break
        except Exception:
            run_failed = True
            is_rag = "rag" in step_type.lower()
            run_error_message = "Retrieval temporarily unavailable" if is_rag else "Step execution failed"
            code = ERROR_CODE_RAG_UNAVAILABLE if is_rag else ERROR_CODE_STEP_FAILED
            update_step(
                client=client,
                step_uuid=step_uuid,
                status=STEP_STATUS_FAILED,
                error_code=code,
                error_message=run_error_message,
                is_retryable=is_rag,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            emit_dry_run_step_failed(client, org_id, user_id, run_id, idx, step_id, code)
            errors.append(run_error_message)
            break

    final_status = RUN_STATUS_FAILED if run_failed else RUN_STATUS_COMPLETED
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
    emit_dry_run_completed(client, org_id, user_id, run_id, final_status)

    return run_id, final_status, step_rows, plan, errors
