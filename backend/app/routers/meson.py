"""Meson build API — interpret wizard requests and deploy agents/workflows (STA-161/164)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.meson_service import (
    MesonDeployResult,
    MesonInterpretResult,
    MesonService,
    get_meson_service,
)

router = APIRouter(prefix="/api/meson", tags=["meson"])


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

    model_config = {"populate_by_name": True}


def _require_org(org_id: str | None) -> str:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return org_id


@router.post("/interpret", response_model=MesonInterpretResult, response_model_by_alias=True)
async def interpret_build_request_route(
    body: MesonInterpretRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
) -> MesonInterpretResult:
    """Turn Meson wizard inputs into an agent/workflow build plan."""
    resolved_org = _require_org(org_id)
    return await meson.interpret_build_request(
        intent=body.intent,
        department=body.department,
        systems=body.systems,
        output_types=body.output_types,
        org_id=resolved_org,
    )


@router.post("/deploy", response_model=MesonDeployResult, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def deploy_build_route(
    body: MesonDeployRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    meson: Annotated[MesonService, Depends(get_meson_service)],
) -> MesonDeployResult:
    """Create agent (+ optional workflow draft) from a Meson build plan."""
    current_user, org_id = admin
    plan = await meson.interpret_build_request(
        intent=body.intent,
        department=body.department,
        systems=body.systems,
        output_types=body.output_types,
        org_id=org_id,
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

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return await meson.deploy_build(
        client=client,
        org_id=org_id,
        user_id=str(current_user.get("user_id") or ""),
        environment_name=environment_name,
        plan=plan,
        create_workflow=body.create_workflow,
    )
