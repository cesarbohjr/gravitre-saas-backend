"""STA-120: Workflow digital twin — fixtures + LLM predictions, no side effects.

INTENTIONAL Module A bypass: simulation terminals must NOT write customer Runs
notifications/learning via ``finalize_execution_outcome``. They use
``emit_dry_run_*`` audit helpers only (see docs/delivery/module-a-dry-run-bypass.md).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.services.connector_fixture_service import lookup_connector_fixture
from app.services.workflow_twin_predictor_service import predict_step_outcome, resolve_step_tool_action
from app.workflows.constants import (
    ERROR_CODE_RAG_UNAVAILABLE,
    ERROR_CODE_STEP_FAILED,
    ERROR_CODE_VALIDATION,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    SCHEMA_VERSION,
    STEP_STATUS_COMPLETED,
    STEP_STATUS_FAILED,
)
from app.workflows.handlers import _truncate_output_snapshot
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
from app.core.safe_dict import safe_normalize_stored_dict

RUN_TYPE_DIGITAL_TWIN = "digital_twin"


async def _simulate_twin_step(
    settings: Settings,
    context: StepContext,
    *,
    objective: str,
    stats: dict[str, int],
) -> dict[str, Any]:
    """Fixture replay, real RAG read, or LLM prediction — never live connector writes."""
    if context.step_type == "rag_retrieve":
        handler = get_handler(context.step_type)
        output = handler.simulate(context)
        stats["ragReads"] = stats.get("ragReads", 0) + 1
        return _truncate_output_snapshot({**output, "source": "live_read", "simulated": True})

    connector_type, action = resolve_step_tool_action(context.step_type, context.config or {})
    if connector_type and action and context.client:
        fixture = lookup_connector_fixture(
            context.client,
            org_id=context.org_id,
            connector_type=connector_type,
            action=action,
            environment=context.environment_name or "production",
        )
        if fixture:
            stats["fixtureHits"] = stats.get("fixtureHits", 0) + 1
            response = safe_normalize_stored_dict(fixture, key='response')
            return _truncate_output_snapshot(
                {
                    **response,
                    "simulated": True,
                    "source": "fixture",
                    "fixtureId": str(fixture["id"]),
                    "connectorType": connector_type,
                    "action": action,
                }
            )

    stats["llmPredictions"] = stats.get("llmPredictions", 0) + 1
    predicted = await predict_step_outcome(
        settings,
        org_id=context.org_id,
        step_type=context.step_type,
        step_name=context.config.get("step_name") if context.config else context.step_id,
        config=context.config or {},
        parameters=context.parameters,
        step_outputs=context.step_outputs,
        objective=objective,
    )
    return _truncate_output_snapshot(predicted)


async def execute_digital_twin(
    settings: Settings,
    org_id: str,
    user_id: str,
    definition: dict[str, Any],
    parameters: dict[str, Any] | None,
    workflow_id: str | None = None,
    environment_name: str = "default",
    workflow_version_id: str | None = None,
) -> tuple[str, str, list[dict], list[dict], list[str], dict[str, int]]:
    """
    Validate, create digital_twin run + steps, simulate with fixtures/LLM.
    Returns (run_id, status, steps, plan, errors, stats).

    INTENTIONAL Module A bypass — terminals use emit_dry_run_* only, not finalize_execution_outcome.
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
        run_type=RUN_TYPE_DIGITAL_TWIN,
    )
    run_id = str(run["id"])
    objective = str(definition.get("name") or definition.get("description") or "Workflow digital twin")
    emit_dry_run_started(client, org_id, user_id, run_id)

    steps_def = definition.get("steps", [])
    plan = [{"step_id": s["id"], "step_name": s["name"]} for s in steps_def]
    step_outputs: dict[str, Any] = {}
    errors: list[str] = []
    stats: dict[str, int] = {"fixtureHits": 0, "llmPredictions": 0, "ragReads": 0}
    run_failed = False
    run_error_message: str | None = None
    now_iso = datetime.now(timezone.utc).isoformat()

    for idx, sdef in enumerate(steps_def):
        step_id = sdef["id"]
        step_name = sdef["name"]
        step_type = sdef["type"]
        config = safe_normalize_stored_dict(sdef, key='config')
        config["step_name"] = step_name
        if isinstance(sdef.get("metadata"), dict):
            config["metadata"] = sdef["metadata"]
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
            output = await _simulate_twin_step(settings, context, objective=objective, stats=stats)
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
        except Exception as e:
            run_failed = True
            is_rag = "rag" in step_type.lower()
            from app.services.canvas_write_gate import (
                CANVAS_WRITE_AUTHORITY_BLOCKED,
                user_facing_message_from_write_authority_error,
            )

            write_gate_msg = user_facing_message_from_write_authority_error(e)
            if write_gate_msg:
                run_error_message = write_gate_msg
                code = CANVAS_WRITE_AUTHORITY_BLOCKED
            elif is_rag:
                run_error_message = "Retrieval temporarily unavailable"
                code = ERROR_CODE_RAG_UNAVAILABLE
            else:
                run_error_message = "Step simulation failed"
                code = ERROR_CODE_STEP_FAILED
            update_step(
                client=client,
                step_uuid=step_uuid,
                status=STEP_STATUS_FAILED,
                error_code=code,
                error_message=run_error_message,
                is_retryable=is_rag and not write_gate_msg,
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

    return run_id, final_status, step_rows, plan, errors, stats
