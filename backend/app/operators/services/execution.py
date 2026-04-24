from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.workflows.repository import get_run_with_steps
from app.routers.workflows import ExecuteRequest, execute_workflow


def resolve_execution_target(
    client,
    org_id: str,
    environment: str,
    primary_context: dict,
    parameters_override: dict | None,
) -> tuple[str, dict]:
    context_type = primary_context.get("type")
    context_id = primary_context.get("id")
    if context_type == "workflow":
        return str(context_id), parameters_override or {}
    if context_type == "run":
        run = get_run_with_steps(client, org_id, str(context_id), environment_name=environment)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
        workflow_id = run.get("workflow_id")
        if not workflow_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Run has no workflow to execute",
            )
        parameters = parameters_override or (run.get("parameters") or {})
        return str(workflow_id), parameters
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Execution supported only for workflow or run context",
    )


async def execute_operator_workflow(
    *,
    workflow_id: str,
    parameters: dict,
    current_user: dict,
    org_id: str,
    environment: str,
    settings,
) -> dict:
    body = ExecuteRequest(workflow_id=UUID(workflow_id), parameters=parameters)
    return await execute_workflow(body, current_user, org_id, environment, settings)
