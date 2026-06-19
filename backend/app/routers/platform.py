"""Platform-operator APIs (Gravitre staff) — Tier 6 CS workspace."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import require_platform_admin
from app.config import Settings, get_settings
from app.services.platform_cs_workspace_service import (
    PlatformCsWorkspaceError,
    assign_platform_tenant,
    backfill_platform_health_snapshots,
    escalate_platform_tenant,
    list_platform_cs_alerts,
    list_platform_tenant_summaries,
    snooze_platform_tenant,
)

router = APIRouter(prefix="/api/platform", tags=["platform"])


class PlatformTenantSummary(BaseModel):
    org_id: str = Field(alias="orgId")
    name: str
    slug: str | None = None
    created_at: str | None = Field(default=None, alias="createdAt")
    health_score: int | None = Field(default=None, alias="healthScore")
    health_grade: str | None = Field(default=None, alias="healthGrade")
    health_recorded_at: str | None = Field(default=None, alias="healthRecordedAt")
    lookback_days: int | None = Field(default=None, alias="lookbackDays")
    risk_count: int = Field(default=0, alias="riskCount")
    open_suggestions: int = Field(default=0, alias="openSuggestions")
    active_failure_alerts: int = Field(default=0, alias="activeFailureAlerts")
    assigned_to: str | None = Field(default=None, alias="assignedTo")
    assigned_email: str | None = Field(default=None, alias="assignedEmail")
    assigned_at: str | None = Field(default=None, alias="assignedAt")
    snoozed_until: str | None = Field(default=None, alias="snoozedUntil")
    is_snoozed: bool = Field(default=False, alias="isSnoozed")
    queue_note: str | None = Field(default=None, alias="queueNote")
    needs_attention: bool = Field(default=False, alias="needsAttention")

    model_config = {"populate_by_name": True}


class PlatformCsWorkspaceSummary(BaseModel):
    total: int
    healthy: int
    at_risk: int = Field(alias="atRisk")
    critical: int
    no_snapshot: int = Field(alias="noSnapshot")
    needs_attention: int = Field(default=0, alias="needsAttention")

    model_config = {"populate_by_name": True}


class PlatformCsWorkspaceResponse(BaseModel):
    tenants: list[PlatformTenantSummary]
    summary: PlatformCsWorkspaceSummary

    model_config = {"populate_by_name": True}


class PlatformTenantAssignRequest(BaseModel):
    assignee_user_id: str | None = Field(default=None, alias="assigneeUserId")
    assignee_email: str | None = Field(default=None, alias="assigneeEmail")
    note: str | None = None


class PlatformTenantSnoozeRequest(BaseModel):
    hours: int = Field(default=24, ge=1, le=336)


class PlatformTenantEscalateRequest(BaseModel):
    note: str | None = None


class PlatformCsAlertItem(BaseModel):
    id: str
    org_id: str = Field(alias="orgId")
    org_name: str = Field(alias="orgName")
    kind: str
    severity: str | None = None
    title: str | None = None
    message: str | None = None
    workflow_id: str | None = Field(default=None, alias="workflowId")
    alert_type: str | None = Field(default=None, alias="alertType")
    suggestion_type: str | None = Field(default=None, alias="suggestionType")
    priority: int | None = None
    occurred_at: str | None = Field(default=None, alias="occurredAt")

    model_config = {"populate_by_name": True}


class PlatformCsAlertsResponse(BaseModel):
    alerts: list[PlatformCsAlertItem]
    count: int

    model_config = {"populate_by_name": True}


@router.get("/cs-workspace/tenants", response_model=PlatformCsWorkspaceResponse, response_model_by_alias=True)
async def get_platform_cs_workspace_tenants(
    _user: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(default=50, ge=1, le=100),
    grade: str | None = Query(default=None),
    hide_snoozed: bool = Query(default=False, alias="hideSnoozed"),
) -> dict[str, Any]:
    """Cross-org integration health rollups for Gravitre platform operators."""
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return list_platform_tenant_summaries(
        client,
        limit=limit,
        grade=grade,
        hide_snoozed=hide_snoozed,
    )


@router.post("/cs-workspace/snapshots/backfill")
async def backfill_platform_cs_snapshots(
    user: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(default=25, ge=1, le=100),
    lookback_days: int = Query(default=30, ge=7, le=90, alias="lookbackDays"),
) -> dict[str, Any]:
    """Record first integration health snapshot for orgs missing history."""
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return backfill_platform_health_snapshots(
        client,
        limit=limit,
        lookback_days=lookback_days,
        actor_id=user["user_id"],
    )


@router.post("/cs-workspace/tenants/{org_id}/assign")
async def assign_platform_cs_tenant(
    org_id: str,
    body: PlatformTenantAssignRequest,
    user: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Assign a tenant to a platform operator for follow-up."""
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    assignee_id = body.assignee_user_id or user["user_id"]
    assignee_email = body.assignee_email or user.get("email")
    try:
        queue = assign_platform_tenant(
            client,
            org_id,
            assignee_user_id=assignee_id,
            assignee_email=assignee_email,
            note=body.note,
            actor_id=user["user_id"],
        )
    except PlatformCsWorkspaceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"queue": queue}


@router.post("/cs-workspace/tenants/{org_id}/snooze")
async def snooze_platform_cs_tenant(
    org_id: str,
    body: PlatformTenantSnoozeRequest,
    user: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Snooze an at-risk tenant from the platform alert queue."""
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        queue = snooze_platform_tenant(
            client,
            org_id,
            hours=body.hours,
            actor_id=user["user_id"],
        )
    except PlatformCsWorkspaceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"queue": queue}


@router.get("/cs-workspace/alerts", response_model=PlatformCsAlertsResponse, response_model_by_alias=True)
async def get_platform_cs_alerts(
    _user: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    alert_type: str | None = Query(default=None, alias="alertType"),
) -> dict[str, Any]:
    """Cross-org open failure alerts and integration suggestions."""
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return list_platform_cs_alerts(client, limit=limit, offset=offset, alert_type=alert_type)


@router.post("/cs-workspace/tenants/{org_id}/escalate")
async def escalate_platform_cs_tenant(
    org_id: str,
    body: PlatformTenantEscalateRequest,
    user: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Escalate a tenant to on-call (Slack/webhook) with CS context."""
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    app_base = (settings.public_app_url or settings.api_public_url or "").strip()
    try:
        return escalate_platform_tenant(
            client,
            org_id,
            actor_id=user["user_id"],
            actor_email=user.get("email"),
            note=body.note,
            webhook_url=settings.platform_cs_escalation_webhook_url,
            app_base_url=app_base or None,
        )
    except PlatformCsWorkspaceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
