"""Meson build API — interpret wizard requests and deploy agents/workflows (STA-161/164/142)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.middleware.entitlements import require_full_seat, require_tier
from app.services.meson_service import (
    MesonAlertsResponse,
    MesonDeployResult,
    MesonFeedbackMetricsResponse,
    MesonFeedbackResult,
    MesonInsightsResponse,
    MesonInterpretResult,
    MesonPageContextResponse,
    MesonPreferencesResponse,
    MesonService,
    MesonSuggestionsResponse,
    get_meson_service,
)

router = APIRouter(
    prefix="/api/meson",
    tags=["meson"],
)

# B1: Meson BUILD requires Control+ plan AND a full seat (Lite may only USE assigned workflows).
_CONTROL_TIER = [Depends(require_tier("control"))]
_MESON_BUILD = [Depends(require_tier("control")), Depends(require_full_seat(action="meson_build"))]


class MesonInterpretRequest(BaseModel):
    intent: str = Field(..., min_length=3, max_length=4000)
    department: str = Field(default="custom", max_length=64)
    systems: list[str] = Field(default_factory=list, max_length=20)
    output_types: list[str] = Field(default_factory=list, alias="outputTypes", max_length=20)

    model_config = {"populate_by_name": True}


class MesonDeployRequest(BaseModel):
    intent: str = Field(..., min_length=3, max_length=4000)
    department: str = Field(default="custom", max_length=64)
    systems: list[str] = Field(default_factory=list, max_length=20)
    output_types: list[str] = Field(default_factory=list, alias="outputTypes", max_length=20)
    generated_config: dict[str, Any] | None = Field(default=None, alias="generatedConfig")
    create_workflow: bool = Field(default=True, alias="createWorkflow")
    icon: str | None = Field(default=None, max_length=50)
    avatar_color: str | None = Field(default=None, alias="avatarColor", max_length=50)

    model_config = {"populate_by_name": True}


class MesonSuggestionsRequest(BaseModel):
    workflow_state: dict[str, Any] | None = Field(default=None, alias="workflowState")
    last_added_node: dict[str, Any] | None = Field(default=None, alias="lastAddedNode")
    workflow_id: str | None = Field(default=None, alias="workflowId")

    model_config = {"populate_by_name": True}


class MesonFeedbackRequest(BaseModel):
    suggestion_id: str = Field(..., alias="suggestionId", min_length=1, max_length=128)
    action: str = Field(..., min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=500)
    workflow_id: str | None = Field(default=None, alias="workflowId")

    model_config = {"populate_by_name": True}


def _require_org(org_id: str | None) -> str:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return org_id


@router.post("/interpret", response_model=MesonInterpretResult, response_model_by_alias=True, dependencies=_MESON_BUILD)
async def interpret_build_request_route(
    body: MesonInterpretRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
) -> MesonInterpretResult:
    """Turn Meson wizard inputs into an agent/workflow build plan."""
    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    user_id = str(_user.get("user_id") or "")
    return await meson.interpret_build_request(
        intent=body.intent,
        department=body.department,
        systems=body.systems,
        output_types=body.output_types,
        org_id=resolved_org,
        user_id=user_id,
        client=client,
    )


@router.post("/deploy", response_model=MesonDeployResult, response_model_by_alias=True, status_code=status.HTTP_201_CREATED, dependencies=_MESON_BUILD)
async def deploy_build_route(
    body: MesonDeployRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
) -> MesonDeployResult:
    """Create agent (+ optional workflow draft) from a Meson build plan."""
    current_user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    user_id = str(current_user.get("user_id") or "")
    plan = await meson.interpret_build_request(
        intent=body.intent,
        department=body.department,
        systems=body.systems,
        output_types=body.output_types,
        org_id=org_id,
        user_id=user_id,
        client=client,
    )
    if body.generated_config:
        cfg = body.generated_config
        plan.generated_config.agent = str(cfg.get("agent") or plan.generated_config.agent)
        if cfg.get("agent_role"):
            plan.generated_config.agent_role = str(cfg.get("agent_role"))
        if cfg.get("agent_description"):
            plan.generated_config.agent_description = str(cfg.get("agent_description"))
        if isinstance(cfg.get("training"), list):
            plan.generated_config.training = [str(x) for x in cfg["training"]]
        if isinstance(cfg.get("workflows"), list):
            plan.generated_config.workflows = [str(x) for x in cfg["workflows"]]
        if isinstance(cfg.get("sample_outputs"), list):
            plan.generated_config.sample_outputs = [str(x) for x in cfg["sample_outputs"]]

    try:
        return await meson.deploy_build(
            client=client,
            org_id=org_id,
            user_id=str(current_user.get("user_id") or ""),
            environment_name=environment_name,
            plan=plan,
            create_workflow=body.create_workflow,
            icon=body.icon,
            avatar_color=body.avatar_color,
        )
    except Exception as exc:  # noqa: BLE001
        from app.workflows.schema import WorkflowValidationError

        if isinstance(exc, WorkflowValidationError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": exc.message, "errors": list(exc.errors or [])},
            ) from exc
        raise


@router.post("/suggestions", response_model=MesonSuggestionsResponse, response_model_by_alias=True, dependencies=_MESON_BUILD)
async def meson_suggestions_route(
    body: MesonSuggestionsRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
) -> MesonSuggestionsResponse:
    """Return next-step node suggestions for the workflow builder."""
    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    feedback_summary = meson.load_feedback_summary(client, resolved_org, workflow_id=body.workflow_id)
    return meson.get_workflow_suggestions(
        workflow_state=body.workflow_state,
        last_added_node=body.last_added_node,
        org_id=resolved_org,
        feedback_summary=feedback_summary,
    )


@router.get("/alerts", response_model=MesonAlertsResponse, response_model_by_alias=True, dependencies=_MESON_BUILD)
async def meson_alerts_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
    workflow_id: Annotated[str | None, Query(alias="workflowId")] = None,
    vendors: Annotated[str | None, Query(description="Comma-separated canvas vendors")] = None,
) -> MesonAlertsResponse:
    """Return proactive workflow and connector alerts (optionally scoped to a workflow)."""
    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    feedback_summary = meson.load_feedback_summary(
        client, resolved_org, workflow_id=workflow_id
    )
    canvas_vendors = {
        part.strip().lower()
        for part in (vendors or "").split(",")
        if part.strip()
    }
    return meson.detect_anomalies(
        client,
        resolved_org,
        environment_name=environment_name,
        settings=settings,
        feedback_summary=feedback_summary,
        workflow_id=workflow_id,
        canvas_vendors=canvas_vendors or None,
    )


@router.get("/insights", response_model=MesonInsightsResponse, response_model_by_alias=True, dependencies=_MESON_BUILD)
async def meson_insights_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
) -> MesonInsightsResponse:
    """Return org-wide Meson insights for the copilot panel."""
    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    feedback_summary = meson.load_feedback_summary(client, resolved_org)
    return meson.get_proactive_insights(
        client,
        resolved_org,
        environment_name=environment_name,
        feedback_summary=feedback_summary,
    )


@router.get("/page-context", response_model=MesonPageContextResponse, response_model_by_alias=True)
async def meson_page_context_route(
    page: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
    entity_id: str | None = None,
) -> MesonPageContextResponse:
    """Return page-scoped Meson insights and suggestions (AI chat, model registry, agents)."""
    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    feedback_summary = meson.load_feedback_summary(client, resolved_org)
    return meson.get_page_context(
        client,
        resolved_org,
        page=page,
        entity_id=entity_id,
        environment_name=environment_name,
        feedback_summary=feedback_summary,
    )


class MesonOptimizationsRequest(BaseModel):
    workflow_state: dict[str, Any] | None = Field(default=None, alias="workflowState")

    model_config = {"populate_by_name": True}


@router.get("/optimizations/{workflow_id}", response_model=MesonInsightsResponse, response_model_by_alias=True)
async def meson_workflow_optimizations_route(
    workflow_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
) -> MesonInsightsResponse:
    """Return workflow-scoped Meson optimization tips for the builder copilot panel."""
    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    feedback_summary = meson.load_feedback_summary(client, resolved_org, workflow_id=workflow_id)
    return meson.get_workflow_optimizations(
        client,
        resolved_org,
        workflow_id,
        environment_name=environment_name,
        feedback_summary=feedback_summary,
    )


@router.post("/optimizations/{workflow_id}", response_model=MesonInsightsResponse, response_model_by_alias=True)
async def meson_workflow_optimizations_with_canvas_route(
    workflow_id: str,
    body: MesonOptimizationsRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
) -> MesonInsightsResponse:
    """Canvas-aware optimizations (tips + insights) for the open workflow."""
    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    feedback_summary = meson.load_feedback_summary(client, resolved_org, workflow_id=workflow_id)
    return meson.get_workflow_optimizations(
        client,
        resolved_org,
        workflow_id,
        environment_name=environment_name,
        feedback_summary=feedback_summary,
        workflow_state=body.workflow_state,
    )


@router.get("/preferences", response_model=MesonPreferencesResponse, response_model_by_alias=True)
async def meson_preferences_route(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
) -> MesonPreferencesResponse:
    """Return learned Meson build preferences for the current user."""
    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return meson.get_user_preferences(
        client,
        resolved_org,
        str(user.get("user_id") or ""),
    )


@router.get("/feedback/metrics", response_model=MesonFeedbackMetricsResponse, response_model_by_alias=True)
async def meson_feedback_metrics_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
    workflow_id: str | None = None,
) -> MesonFeedbackMetricsResponse:
    """Return Meson suggestion accept/dismiss metrics for the org or a workflow."""
    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return meson.get_feedback_metrics(client, resolved_org, workflow_id=workflow_id)


@router.post("/feedback", response_model=MesonFeedbackResult)
async def meson_feedback_route(
    body: MesonFeedbackRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
) -> MesonFeedbackResult:
    """Record accept/dismiss feedback for Meson suggestions."""
    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return meson.record_feedback(
            client,
            resolved_org,
            str(user.get("user_id") or ""),
            suggestion_id=body.suggestion_id,
            action=body.action,
            reason=body.reason,
            workflow_id=body.workflow_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


class MesonEditRequest(BaseModel):
    workflow_id: str = Field(..., alias="workflowId", min_length=1, max_length=64)
    instruction: str = Field(..., min_length=3, max_length=4000)
    workflow_state: dict[str, Any] | None = Field(default=None, alias="workflowState")

    model_config = {"populate_by_name": True}


class MesonEditApplyRequest(BaseModel):
    workflow_id: str = Field(..., alias="workflowId", min_length=1, max_length=64)
    proposal_id: str = Field(..., alias="proposalId", min_length=1, max_length=64)

    model_config = {"populate_by_name": True}


@router.post("/edit", dependencies=_MESON_BUILD)
async def meson_edit_propose_route(
    body: MesonEditRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Propose a natural-language edit against an existing saved canvas (reviewable diff)."""
    from app.services.meson_canvas_edit import propose_workflow_edit

    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        proposal = await propose_workflow_edit(
            client=client,
            settings=settings,
            org_id=resolved_org,
            workflow_id=body.workflow_id,
            environment_name=environment_name,
            instruction=body.instruction,
            workflow_state=body.workflow_state,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return proposal.model_dump(by_alias=True)


@router.post("/edit/apply", dependencies=_MESON_BUILD)
async def meson_edit_apply_route(
    body: MesonEditApplyRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Apply a previously proposed canvas edit (creates a new workflow version)."""
    from app.services.meson_canvas_edit import apply_workflow_edit

    current_user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        result = apply_workflow_edit(
            client=client,
            org_id=org_id,
            workflow_id=body.workflow_id,
            environment_name=environment_name,
            proposal_id=body.proposal_id,
            created_by=str(current_user.get("user_id") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result.model_dump(by_alias=True)


@router.get("/edit/history/{workflow_id}", dependencies=_MESON_BUILD)
async def meson_edit_history_route(
    workflow_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
) -> dict[str, Any]:
    """List recent in-session conversational edit proposals (undo foundation)."""
    from app.services.meson_canvas_edit import list_edit_proposals

    resolved_org = _require_org(org_id)
    return {"proposals": list_edit_proposals(resolved_org, workflow_id)}


@router.post("/explain/{workflow_id}", dependencies=_MESON_BUILD)
async def meson_explain_workflow_route(
    workflow_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Plain-language explanation of the real canvas graph (Phase 5.1)."""
    from app.services.meson_canvas_edit import explain_workflow

    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        result = await explain_workflow(
            client=client,
            org_id=resolved_org,
            workflow_id=workflow_id,
            environment_name=environment_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return result.model_dump(by_alias=True)


@router.get("/node-reliability/{workflow_id}", dependencies=_MESON_BUILD)
async def meson_node_reliability_route(
    workflow_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Per-node failure rates + cross-workflow failure patterns (Phase 5.2/5.3)."""
    from app.services.canvas_node_reliability import node_reliability_for_workflow

    resolved_org = _require_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return node_reliability_for_workflow(client, org_id=resolved_org, workflow_id=workflow_id)
