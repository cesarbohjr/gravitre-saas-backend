from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.operator.schemas import (
    ActionPlanRequest,
    ActionPlanResponse,
    ConnectorContextResponse,
    RunContextResponse,
    SourceContextResponse,
    WorkflowContextResponse,
)
from app.operator.services.action_plans import build_action_plan
from app.operator.services.context_packs import (
    build_connector_context,
    build_run_context,
    build_source_context,
    build_workflow_context,
)

router = APIRouter(prefix="/api/operator", tags=["operator"])


def _pack_summary(
    pack_type: str,
    pack_id: str,
    title: str,
    summary: str,
    status: str,
    environment: str,
    href: str,
) -> dict:
    return {
        "id": pack_id,
        "type": pack_type,
        "title": title,
        "summary": summary,
        "status": status,
        "environment": environment,
        "href": href,
    }


@router.get("/context/run/{run_id}", response_model=RunContextResponse)
async def get_run_context(
    run_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RunContextResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    context = build_run_context(client, settings, org_id, environment, str(run_id))
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    run = context["run"]
    pack = _pack_summary(
        "run",
        str(run_id),
        f"Run {str(run_id)[:8]}",
        f"Run status: {run.get('status')}",
        "ready",
        environment,
        f"/runs/{run_id}",
    )
    return RunContextResponse(
        pack=pack,
        run=run,
        steps=context["steps"],
        recent_runs=context["recent_runs"],
        audit=context["audit"],
        environment=environment,
    )


@router.get("/context/workflow/{workflow_id}", response_model=WorkflowContextResponse)
async def get_workflow_context(
    workflow_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkflowContextResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    context = build_workflow_context(client, org_id, environment, str(workflow_id))
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    workflow = context["workflow"]
    pack = _pack_summary(
        "workflow",
        str(workflow_id),
        workflow.get("name") or f"Workflow {str(workflow_id)[:8]}",
        "Workflow definition and recent versions.",
        "ready",
        environment,
        f"/workflows/{workflow_id}",
    )
    return WorkflowContextResponse(
        pack=pack,
        workflow=workflow,
        active_version=context["active_version"],
        recent_versions=context["recent_versions"],
        recent_runs=context["recent_runs"],
        linked_connectors=context["linked_connectors"],
        environment=environment,
    )


@router.get("/context/connector/{connector_id}", response_model=ConnectorContextResponse)
async def get_connector_context(
    connector_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConnectorContextResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    context = build_connector_context(client, org_id, environment, str(connector_id))
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    connector = context["connector"]
    pack = _pack_summary(
        "connector",
        str(connector_id),
        f"{connector.get('type', 'connector').title()} Integration",
        "Integration health and configuration summary.",
        "ready",
        environment,
        f"/integrations/{connector_id}",
    )
    return ConnectorContextResponse(
        pack=pack,
        connector=connector,
        config_summary=context["config_summary"],
        related_workflows=context["related_workflows"],
        environment=environment,
    )


@router.get("/context/source/{source_id}", response_model=SourceContextResponse)
async def get_source_context(
    source_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SourceContextResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    context = build_source_context(client, org_id, environment, str(source_id))
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    source = context["source"]
    pack = _pack_summary(
        "source",
        str(source_id),
        source.get("title") or f"Source {str(source_id)[:8]}",
        "Source freshness and recent documents.",
        "ready",
        environment,
        f"/sources/{source_id}",
    )
    return SourceContextResponse(
        pack=pack,
        source=source,
        recent_documents=context["recent_documents"],
        ingest_jobs=context["ingest_jobs"],
        environment=environment,
    )


@router.get("/prompts")
async def list_operator_prompts(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows = (
        client.table("operator_prompts")
        .select("id, icon, label, prompt, order_index")
        .eq("org_id", org_id)
        .eq("is_active", True)
        .order("order_index", desc=False)
        .execute()
        .data
        or []
    )
    return {
        "prompts": [
            {
                "id": str(row["id"]),
                "icon": row.get("icon") or "",
                "label": row.get("label") or "",
                "prompt": row.get("prompt") or "",
            }
            for row in rows
        ]
    }


@router.post("/action-plan", response_model=ActionPlanResponse)
async def create_action_plan(
    body: ActionPlanRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActionPlanResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        plan = build_action_plan(
            client=client,
            settings=settings,
            org_id=org_id,
            environment=environment,
            primary_context=body.primary_context.model_dump(),
            related_contexts=[c.model_dump() for c in body.related_contexts],
            operator_goal=body.operator_goal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ActionPlanResponse(**plan)
