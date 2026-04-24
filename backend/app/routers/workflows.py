"""BE-11: Workflow dry-run and read APIs. Auth required; org from context only.
BE-20: Execute, approve, reject endpoints."""
import time
from datetime import datetime, timezone, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.billing.service import (
    apply_usage_with_overage,
    build_ai_usage_metadata,
    get_current_period,
    get_default_usage_quantity,
    get_plan_for_org,
    require_feature,
    require_limit,
)
from app.config import Settings, get_settings
from app.core.logging import get_logger, request_id_ctx
from app.workflows.constants import (
    ERROR_CODE_RAG_UNAVAILABLE,
    RUN_STATUS_PENDING_APPROVAL,
    RUN_STATUS_RUNNING,
    RUN_TYPE_EXECUTE,
    SCHEMA_VERSION,
)
from app.workflows.dry_run import execute_dry_run
from app.workflows.execute import execute_workflow_steps
from app.policy.engine import (
    PolicyContext,
    can_activate_workflow_version,
    can_manage_workflow_versions,
    can_promote_workflow_version,
    evaluate_policy,
)
from app.workflows.policy import (
    PolicyResolutionError,
    check_concurrency,
    get_user_role,
    resolve_policy,
    validate_execute_steps,
)
from app.workflows.audit import write_audit_event
from app.workflows.constants import RESOURCE_TYPE_WORKFLOW_RUN
from app.workflows.repository import (
    create_execute_run,
    create_step,
    emit_execute_approved,
    emit_execute_created,
    emit_execute_pending_approval,
    emit_execute_rejected,
    emit_execute_started,
    emit_execute_cancelled,
    get_approval_counts,
    get_run_with_steps,
    get_supabase_client,
    get_workflow_def,
    get_active_workflow_version,
    get_next_workflow_version_number,
    get_workflow_version,
    get_workflow_node,
    get_workflow_edge,
    insert_run_approval,
    list_workflow_nodes,
    list_workflow_edges,
    list_workflow_versions,
    list_workflow_schedules,
    create_workflow_node,
    create_workflow_edge,
    create_workflow_version,
    create_workflow_schedule,
    list_workflows,
    get_workflow_schedule,
    set_active_workflow_version,
    try_mark_run_running,
    update_workflow_schedule,
    update_workflow_node,
    delete_workflow_node,
    delete_workflow_edge,
    delete_workflow_schedule,
    update_run,
)
from app.connectors.repository import get_connector
from app.operators.repository import get_operator
from app.rag.ingest import get_source
from app.workflows.schema import (
    WorkflowValidationError,
    compute_run_hash,
    validate_definition,
    validate_parameters,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])
approvals_router = APIRouter(prefix="/api/approvals", tags=["approvals"])
runs_router = APIRouter(prefix="/api/runs", tags=["runs"])


class DryRunRequest(BaseModel):
    workflow_id: UUID | None = Field(default=None, description="Use stored definition; omit for inline")
    definition: dict | None = Field(default=None, description="Inline definition when workflow_id omitted")
    parameters: dict | None = Field(default=None)


class ExecuteRequest(BaseModel):
    workflow_id: UUID = Field(..., description="Required workflow to execute")
    parameters: dict | None = Field(default=None)


class ApproveRejectRequest(BaseModel):
    comment: str | None = Field(default=None)


class ScheduleCreateRequest(BaseModel):
    cron_expression: str | None = Field(default=None, min_length=1)
    cronExpression: str | None = Field(default=None, alias="cronExpression")
    enabled: bool | None = None
    is_enabled: bool | None = None


class ScheduleUpdateRequest(BaseModel):
    cron_expression: str | None = Field(default=None, min_length=1)
    cronExpression: str | None = Field(default=None, alias="cronExpression")
    enabled: bool | None = None
    is_enabled: bool | None = None


class WorkflowVersionItem(BaseModel):
    id: str
    version: int
    created_at: str
    created_by: str | None
    schema_version: str


class WorkflowActiveVersion(BaseModel):
    id: str
    version: int
    created_at: str
    created_by: str | None
    schema_version: str
    definition: dict


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    goal: str | None = None
    environment_id: str | None = Field(default=None, alias="environmentId")


class WorkflowUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    goal: str | None = None
    status: str | None = None
    version: str | None = None


class WorkflowStageUpdateRequest(BaseModel):
    stage: str = Field(..., pattern="^(build|review|activate|run)$")


class WorkflowAiStepRequest(BaseModel):
    step_id: str = Field(..., alias="stepId")


class WorkflowAiSuggestRequest(BaseModel):
    after_step_id: str | None = Field(default=None, alias="afterStepId")


class WorkflowAiChatRequest(BaseModel):
    message: str


class WorkflowNodeCreateRequest(BaseModel):
    node_type: str | None = Field(default=None, pattern="^(agent|task|connector|tool|source|approval)$")
    type: str | None = Field(default=None, alias="type")
    title: str = Field(..., min_length=1)
    name: str | None = None
    instruction: str | None = None
    description: str | None = None
    config: dict | None = None
    system_icon: str | None = Field(default=None, alias="systemIcon")
    system_name: str | None = Field(default=None, alias="systemName")
    has_approval_gate: bool | None = Field(default=None, alias="hasApprovalGate")
    inputs: list[dict] | None = None
    outputs: list[dict] | None = None
    guardrails: list[dict] | None = None
    status: str | None = None
    operator_id: UUID | None = None
    connector_id: UUID | None = None
    source_id: UUID | None = None
    tool_type: str | None = None
    tool_config: dict | None = None
    position: dict | None = None
    position_x: float | None = Field(default=None, alias="positionX")
    position_y: float | None = Field(default=None, alias="positionY")
    order_index: int | None = Field(default=None, alias="orderIndex")
    metadata: dict | None = None


class WorkflowNodeUpdateRequest(BaseModel):
    node_type: str | None = Field(None, pattern="^(agent|task|connector|tool|source|approval)$")
    type: str | None = Field(default=None, alias="type")
    title: str | None = None
    name: str | None = None
    instruction: str | None = None
    description: str | None = None
    config: dict | None = None
    system_icon: str | None = Field(default=None, alias="systemIcon")
    system_name: str | None = Field(default=None, alias="systemName")
    has_approval_gate: bool | None = Field(default=None, alias="hasApprovalGate")
    inputs: list[dict] | None = None
    outputs: list[dict] | None = None
    guardrails: list[dict] | None = None
    status: str | None = None
    operator_id: UUID | None = None
    connector_id: UUID | None = None
    source_id: UUID | None = None
    tool_type: str | None = None
    tool_config: dict | None = None
    position: dict | None = None
    position_x: float | None = Field(default=None, alias="positionX")
    position_y: float | None = Field(default=None, alias="positionY")
    order_index: int | None = Field(default=None, alias="orderIndex")
    metadata: dict | None = None


class WorkflowEdgeCreateRequest(BaseModel):
    from_node_id: UUID
    to_node_id: UUID
    fromNodeId: UUID | None = Field(default=None, alias="fromNodeId")
    toNodeId: UUID | None = Field(default=None, alias="toNodeId")
    edge_type: str = Field(..., pattern="^(sequence|branch|condition)$")
    condition: dict | None = None


class WorkflowNodePositionUpdate(BaseModel):
    id: UUID
    position: dict | None = None
    position_x: float | None = None
    position_y: float | None = None


class WorkflowNodePositionsUpdateRequest(BaseModel):
    nodes: list[WorkflowNodePositionUpdate]


def _operator_allowed(operator: dict, environment: str) -> bool:
    allowed = operator.get("allowed_environments") or []
    if not allowed:
        return True
    return environment in allowed


def _node_out(node: dict) -> dict:
    position = node.get("position") if isinstance(node.get("position"), dict) else {}
    position_x = node.get("position_x")
    position_y = node.get("position_y")
    if position_x is None and isinstance(position, dict):
        position_x = position.get("x")
    if position_y is None and isinstance(position, dict):
        position_y = position.get("y")
    return {
        "id": str(node["id"]),
        "workflow_id": str(node["workflow_id"]),
        "node_type": node.get("node_type") or "",
        "type": node.get("node_type") or "",
        "title": node.get("title") or "",
        "name": node.get("name") or node.get("title") or "",
        "description": node.get("description") or node.get("instruction"),
        "instruction": node.get("instruction"),
        "config": node.get("config") or {},
        "systemIcon": node.get("system_icon"),
        "systemName": node.get("system_name"),
        "hasApprovalGate": bool(node.get("has_approval_gate")),
        "inputs": node.get("inputs") or [],
        "outputs": node.get("outputs") or [],
        "guardrails": node.get("guardrails") or [],
        "status": node.get("status") or "needs_config",
        "operator_id": str(node["operator_id"]) if node.get("operator_id") else None,
        "connector_id": str(node["connector_id"]) if node.get("connector_id") else None,
        "source_id": str(node["source_id"]) if node.get("source_id") else None,
        "tool_type": node.get("tool_type"),
        "tool_config": node.get("tool_config"),
        "position": node.get("position"),
        "position_x": position_x,
        "position_y": position_y,
        "order_index": node.get("order_index") or 0,
        "metadata": node.get("metadata"),
        "environment": node.get("environment"),
        "created_at": node.get("created_at"),
        "updated_at": node.get("updated_at"),
    }


def _edge_out(edge: dict) -> dict:
    return {
        "id": str(edge["id"]),
        "workflow_id": str(edge["workflow_id"]),
        "from_node_id": str(edge["from_node_id"]),
        "to_node_id": str(edge["to_node_id"]),
        "fromNodeId": str(edge["from_node_id"]),
        "toNodeId": str(edge["to_node_id"]),
        "edge_type": edge.get("edge_type") or "",
        "condition": edge.get("condition"),
        "environment": edge.get("environment"),
        "created_at": edge.get("created_at"),
    }


def _record_workflow_run_usage(client, org_id: str, environment_name: str, plan: dict) -> None:
    period_start, period_end = get_current_period()
    apply_usage_with_overage(
        client=client,
        org_id=org_id,
        environment=environment_name,
        metric_type="workflow_runs",
        quantity=get_default_usage_quantity("workflow_runs"),
        plan=plan,
        period_start=period_start,
        period_end=period_end,
    )


def _generate_goal(name: str, description: str | None = None) -> str:
    base = (name or "").strip().replace("_", " ").replace("-", " ")
    if not base:
        return "Automate workflow execution"
    lower = base.lower()
    if "salesforce" in lower and "sync" in lower:
        return "Sync customer data from Salesforce to internal systems"
    if "sync" in lower:
        target = base.lower().replace("sync", "").strip()
        target = target or "data"
        return f"Sync {target} data across systems".title()
    return f"Automate {base}"


class PromoteVersionRequest(BaseModel):
    to_environment: str = Field(..., min_length=1)


def _next_hour(base: datetime) -> datetime:
    return (base.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))


def _next_day(base: datetime) -> datetime:
    next_day = base.date() + timedelta(days=1)
    return datetime.combine(next_day, datetime.min.time(), tzinfo=timezone.utc)


def _next_week(base: datetime) -> datetime:
    # Next Sunday at 00:00 UTC
    days_ahead = (6 - base.weekday()) % 7
    days_ahead = 7 if days_ahead == 0 else days_ahead
    target = base.date() + timedelta(days=days_ahead)
    return datetime.combine(target, datetime.min.time(), tzinfo=timezone.utc)


def _next_month(base: datetime) -> datetime:
    year = base.year + (1 if base.month == 12 else 0)
    month = 1 if base.month == 12 else base.month + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def compute_next_run_at(cron_expression: str, base: datetime | None = None) -> str | None:
    """Best-effort next_run_at for common cron patterns. Returns ISO or None."""
    if base is None:
        base = datetime.now(timezone.utc)
    expr = cron_expression.strip()
    if not expr:
        return None
    if expr == "@hourly":
        return _next_hour(base).isoformat()
    if expr == "@daily":
        return _next_day(base).isoformat()
    if expr == "@weekly":
        return _next_week(base).isoformat()
    if expr == "@monthly":
        return _next_month(base).isoformat()
    parts = expr.split()
    if len(parts) != 5:
        return None
    minute, hour, dom, month, dow = parts
    if minute.startswith("*/") and hour == "*" and dom == "*" and month == "*" and dow == "*":
        try:
            interval = int(minute.replace("*/", ""))
        except ValueError:
            return None
        if interval <= 0:
            return None
        base_floor = base.replace(second=0, microsecond=0)
        minutes_since_hour = base_floor.minute
        next_minute = ((minutes_since_hour // interval) + 1) * interval
        next_time = base_floor
        if next_minute >= 60:
            next_time = next_time.replace(minute=0) + timedelta(hours=1)
        else:
            next_time = next_time.replace(minute=next_minute)
        return next_time.isoformat()
    if minute == "0" and hour == "*" and dom == "*" and month == "*" and dow == "*":
        return _next_hour(base).isoformat()
    if minute == "0" and hour == "0" and dom == "*" and month == "*" and dow == "*":
        return _next_day(base).isoformat()
    if minute == "0" and hour == "0" and dom == "*" and month == "*" and dow in {"0", "7"}:
        return _next_week(base).isoformat()
    if minute == "0" and hour == "0" and dom == "1" and month == "*" and dow == "*":
        return _next_month(base).isoformat()
    return None


class StepOut(BaseModel):
    id: str
    step_id: str
    step_index: int
    step_name: str
    step_type: str
    status: str
    input_snapshot: dict | None
    output_snapshot: dict | None
    error_code: str | None
    error_message: str | None
    is_retryable: bool
    started_at: str | None
    completed_at: str | None


class DryRunResponse(BaseModel):
    run_id: str
    status: str
    plan: list[dict]
    steps: list[StepOut]
    errors: list[str] = []


class WorkflowVersionListResponse(BaseModel):
    versions: list[WorkflowVersionItem]


def _step_to_out(s: dict) -> StepOut:
    return StepOut(
        id=str(s["id"]),
        step_id=s.get("step_id", ""),
        step_index=s.get("step_index", 0),
        step_name=s.get("step_name", ""),
        step_type=s.get("step_type", ""),
        status=s.get("status", ""),
        input_snapshot=s.get("input_snapshot"),
        output_snapshot=s.get("output_snapshot"),
        error_code=s.get("error_code"),
        error_message=s.get("error_message"),
        is_retryable=s.get("is_retryable", False),
        started_at=s.get("started_at"),
        completed_at=s.get("completed_at"),
    )


def _run_step_out(s: dict) -> dict:
    return {
        "id": str(s["id"]),
        "nodeId": str(s.get("node_id")) if s.get("node_id") else None,
        "name": s.get("name") or s.get("step_name") or "",
        "status": s.get("status") or "pending",
        "startedAt": s.get("started_at"),
        "completedAt": s.get("completed_at"),
        "logs": s.get("logs"),
        "errorMessage": s.get("error_message"),
        "orderIndex": s.get("order_index") or s.get("step_index") or 0,
    }


@router.get("/{workflow_id}/nodes")
async def list_workflow_nodes_route(
    workflow_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    plan = get_plan_for_org(client, org_id)
    wf = get_workflow_def(client, org_id, str(workflow_id))
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    nodes = list_workflow_nodes(client, org_id, str(workflow_id), environment_name)
    return {"nodes": [_node_out(node) for node in nodes]}


@router.get("/{workflow_id}/builder")
async def get_workflow_builder(
    workflow_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Return full orchestration graph for the visual builder."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    wf = get_workflow_def(client, org_id, str(workflow_id))
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    nodes = list_workflow_nodes(client, org_id, str(workflow_id), environment_name)
    edges = list_workflow_edges(client, org_id, str(workflow_id), environment_name)
    return {"workflow_id": str(workflow_id), "nodes": [_node_out(n) for n in nodes], "edges": [_edge_out(e) for e in edges]}


@router.post("/{workflow_id}/nodes", status_code=status.HTTP_201_CREATED)
async def create_workflow_node_route(
    workflow_id: UUID,
    body: WorkflowNodeCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    wf = get_workflow_def(client, org_id, str(workflow_id))
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    if body.operator_id is not None:
        operator = get_operator(client, org_id, str(body.operator_id))
        if not operator:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
        if not _operator_allowed(operator, environment_name):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    if body.connector_id is not None:
        connector = get_connector(client, org_id, str(body.connector_id), environment_name=environment_name)
        if not connector:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if body.source_id is not None:
        source = get_source(client, org_id, str(body.source_id), environment_name=environment_name)
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    payload = body.dict(by_alias=True)
    if payload.get("type") and not payload.get("node_type"):
        payload["node_type"] = payload.get("type")
    if payload.get("systemIcon") and not payload.get("system_icon"):
        payload["system_icon"] = payload.get("systemIcon")
    if payload.get("systemName") and not payload.get("system_name"):
        payload["system_name"] = payload.get("systemName")
    if payload.get("hasApprovalGate") is not None and "has_approval_gate" not in payload:
        payload["has_approval_gate"] = payload.get("hasApprovalGate")
    if not payload.get("node_type"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node_type required")
    if payload.get("name") and not payload.get("title"):
        payload["title"] = payload["name"]
    if payload.get("description") and not payload.get("instruction"):
        payload["instruction"] = payload["description"]
    if payload.get("inputs") is None and isinstance(payload.get("config"), dict):
        payload["inputs"] = payload["config"].get("inputs")
    if payload.get("outputs") is None and isinstance(payload.get("config"), dict):
        payload["outputs"] = payload["config"].get("outputs")
    if payload.get("guardrails") is None and isinstance(payload.get("config"), dict):
        payload["guardrails"] = payload["config"].get("guardrails")
    if payload.get("position") is None and (payload.get("position_x") is not None or payload.get("position_y") is not None):
        payload["position"] = {
            "x": payload.get("position_x") or 0,
            "y": payload.get("position_y") or 0,
        }
    if payload.get("operator_id") is not None:
        payload["operator_id"] = str(payload["operator_id"])
    if payload.get("connector_id") is not None:
        payload["connector_id"] = str(payload["connector_id"])
    if payload.get("source_id") is not None:
        payload["source_id"] = str(payload["source_id"])
    created = create_workflow_node(
        client,
        org_id=org_id,
        workflow_id=str(workflow_id),
        environment_name=environment_name,
        payload=payload,
        created_by=_user.get("user_id"),
    )
    return _node_out(created)


@router.patch("/{workflow_id}/nodes")
async def update_workflow_node_positions(
    workflow_id: UUID,
    body: WorkflowNodePositionsUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Bulk update node positions for drag interactions."""
    _user, org_id = _admin
    client = get_supabase_client(settings)
    wf = get_workflow_def(client, org_id, str(workflow_id))
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    updated_nodes: list[dict] = []
    for node_update in body.nodes:
        node = get_workflow_node(client, org_id, str(node_update.id), environment_name)
        if not node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
        if str(node.get("workflow_id")) != str(workflow_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Node does not belong to workflow")
        position = node_update.position
        if position is None and (node_update.position_x is not None or node_update.position_y is not None):
            position = {
                "x": node_update.position_x or 0,
                "y": node_update.position_y or 0,
            }
        if position is None:
            continue
        updated = update_workflow_node(
            client,
            org_id=org_id,
            node_id=str(node_update.id),
            environment_name=environment_name,
            payload={
                "position": position,
                "position_x": position.get("x") if isinstance(position, dict) else None,
                "position_y": position.get("y") if isinstance(position, dict) else None,
            },
            updated_by=_user.get("user_id"),
        )
        if updated:
            updated_nodes.append(_node_out(updated))
    return {"nodes": updated_nodes}


@router.patch("/nodes/{node_id}")
async def update_workflow_node_route(
    node_id: UUID,
    body: WorkflowNodeUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    node = get_workflow_node(client, org_id, str(node_id), environment_name)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    payload = body.dict(exclude_unset=True, by_alias=True)
    if payload.get("type") and "node_type" not in payload:
        payload["node_type"] = payload.get("type")
    if payload.get("systemIcon") and "system_icon" not in payload:
        payload["system_icon"] = payload.get("systemIcon")
    if payload.get("systemName") and "system_name" not in payload:
        payload["system_name"] = payload.get("systemName")
    if payload.get("hasApprovalGate") is not None and "has_approval_gate" not in payload:
        payload["has_approval_gate"] = payload.get("hasApprovalGate")
    if "name" in payload and payload.get("name") and "title" not in payload:
        payload["title"] = payload.get("name")
    if "description" in payload and payload.get("description") and "instruction" not in payload:
        payload["instruction"] = payload.get("description")
    if "inputs" not in payload and isinstance(payload.get("config"), dict):
        payload["inputs"] = payload["config"].get("inputs")
    if "outputs" not in payload and isinstance(payload.get("config"), dict):
        payload["outputs"] = payload["config"].get("outputs")
    if "guardrails" not in payload and isinstance(payload.get("config"), dict):
        payload["guardrails"] = payload["config"].get("guardrails")
    if payload.get("position") is None and (payload.get("position_x") is not None or payload.get("position_y") is not None):
        payload["position"] = {
            "x": payload.get("position_x") or 0,
            "y": payload.get("position_y") or 0,
        }
    if "operator_id" in payload and payload["operator_id"] is not None:
        operator = get_operator(client, org_id, str(payload["operator_id"]))
        if not operator:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
        if not _operator_allowed(operator, environment_name):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
        payload["operator_id"] = str(payload["operator_id"])
    if "connector_id" in payload and payload["connector_id"] is not None:
        connector = get_connector(client, org_id, str(payload["connector_id"]), environment_name=environment_name)
        if not connector:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
        payload["connector_id"] = str(payload["connector_id"])
    if "source_id" in payload and payload["source_id"] is not None:
        source = get_source(client, org_id, str(payload["source_id"]), environment_name=environment_name)
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        payload["source_id"] = str(payload["source_id"])
    updated = update_workflow_node(
        client,
        org_id=org_id,
        node_id=str(node_id),
        environment_name=environment_name,
        payload=payload,
        updated_by=_user.get("user_id"),
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return _node_out(updated)


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_node_route(
    node_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    node = get_workflow_node(client, org_id, str(node_id), environment_name)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    removed = delete_workflow_node(client, org_id, str(node_id), environment_name)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return None


@router.delete("/{workflow_id}/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_node_alias(
    workflow_id: UUID,
    node_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    node = get_workflow_node(get_supabase_client(settings), _admin[1], str(node_id), environment_name)
    if node and str(node.get("workflow_id")) != str(workflow_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Node does not belong to workflow")
    return await delete_workflow_node_route(node_id, _admin, environment_name, settings)


@router.get("/{workflow_id}/edges")
async def list_workflow_edges_route(
    workflow_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    wf = get_workflow_def(client, org_id, str(workflow_id))
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    edges = list_workflow_edges(client, org_id, str(workflow_id), environment_name)
    return {"edges": [_edge_out(edge) for edge in edges]}


@router.post("/{workflow_id}/edges", status_code=status.HTTP_201_CREATED)
async def create_workflow_edge_route(
    workflow_id: UUID,
    body: WorkflowEdgeCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    wf = get_workflow_def(client, org_id, str(workflow_id))
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    from_id = body.fromNodeId or body.from_node_id
    to_id = body.toNodeId or body.to_node_id
    from_node = get_workflow_node(client, org_id, str(from_id), environment_name)
    to_node = get_workflow_node(client, org_id, str(to_id), environment_name)
    if not from_node or not to_node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    if str(from_node.get("workflow_id")) != str(workflow_id) or str(to_node.get("workflow_id")) != str(workflow_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nodes must belong to workflow")
    payload = body.dict(by_alias=True)
    payload["from_node_id"] = str(from_id)
    payload["to_node_id"] = str(to_id)
    created = create_workflow_edge(
        client,
        org_id=org_id,
        workflow_id=str(workflow_id),
        environment_name=environment_name,
        payload=payload,
        created_by=_user.get("user_id"),
    )
    return _edge_out(created)


@router.delete("/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_edge_route(
    edge_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    edge = get_workflow_edge(client, org_id, str(edge_id), environment_name)
    if not edge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge not found")
    removed = delete_workflow_edge(client, org_id, str(edge_id), environment_name)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge not found")
    return None


@router.post("/{workflow_id}/connections", status_code=status.HTTP_201_CREATED)
async def create_workflow_connection_route(
    workflow_id: UUID,
    body: WorkflowEdgeCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Alias for edge creation to match builder API."""
    return await create_workflow_edge_route(workflow_id, body, _admin, environment_name, settings)


@router.delete("/{workflow_id}/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_connection_route(
    workflow_id: UUID,
    connection_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Alias for edge deletion to match builder API."""
    edge = get_workflow_edge(get_supabase_client(settings), _admin[1], str(connection_id), environment_name)
    if edge and str(edge.get("workflow_id")) != str(workflow_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection does not belong to workflow")
    return await delete_workflow_edge_route(connection_id, _admin, environment_name, settings)


@router.post("/dry-run", response_model=DryRunResponse)
async def dry_run(
    body: DryRunRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DryRunResponse:
    """Validate and dry-run a workflow. Org from auth; no external side effects."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    if settings.disable_execute:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Execute is disabled")
    if settings.disable_execute:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Execute is disabled")
    start = time.perf_counter()
    definition: dict | None = body.definition
    workflow_id: str | None = str(body.workflow_id) if body.workflow_id else None
    if workflow_id:
        client = get_supabase_client(settings)
        wf = get_workflow_def(client, org_id, workflow_id)
        if not wf:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found",
            )
        active = get_active_workflow_version(client, org_id, workflow_id, environment_name)
        if not active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No active workflow version. Create and activate a version first.",
            )
        definition = active.get("definition")
        if not definition:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active workflow definition missing",
            )
        workflow_version_id = str(active["id"])
    else:
        workflow_version_id = None
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide workflow_id or definition",
        )
    try:
        run_id, run_status, step_rows, plan, errors = execute_dry_run(
            settings=settings,
            org_id=org_id,
            user_id=current_user["user_id"],
            definition=definition,
            parameters=body.parameters,
            workflow_id=workflow_id,
            environment_name=environment_name,
            workflow_version_id=workflow_version_id,
        )
    except WorkflowValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from e
    latency_ms = int((time.perf_counter() - start) * 1000)
    steps_out = [_step_to_out(s) for s in step_rows]
    rag_failed = any(
        s.get("error_code") == ERROR_CODE_RAG_UNAVAILABLE
        for s in step_rows
    )
    if rag_failed:
        logger.info(
            "workflow_dry_run request_id=%s org_id=%s run_id=%s latency_ms=%s step_count=%s status=%s",
            request_id_ctx.get(),
            org_id,
            run_id,
            latency_ms,
            len(step_rows),
            run_status,
            extra={
                "request_id": request_id_ctx.get(),
                "org_id": org_id,
                "run_id": run_id,
                "latency_ms": latency_ms,
                "step_count": len(step_rows),
                "status": run_status,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrieval temporarily unavailable",
        )
    logger.info(
        "workflow_dry_run request_id=%s org_id=%s run_id=%s latency_ms=%s step_count=%s status=%s",
        request_id_ctx.get(),
        org_id,
        run_id,
        latency_ms,
        len(step_rows),
        run_status,
        extra={
            "request_id": request_id_ctx.get(),
            "org_id": org_id,
            "run_id": run_id,
            "latency_ms": latency_ms,
            "step_count": len(step_rows),
            "status": run_status,
        },
    )
    return DryRunResponse(
        run_id=run_id,
        status=run_status,
        plan=plan,
        steps=steps_out,
        errors=errors,
    )


@router.post("/{workflow_id}/versions")
async def create_workflow_version_route(
    workflow_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Create immutable workflow version from stored definition."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "versioning")
    wf = get_workflow_def(client, org_id, str(workflow_id))
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as e:
        logger.error("version_role_failure org_id=%s user_id=%s error=%s stop_condition", org_id, current_user["user_id"], e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from e
    if not can_manage_workflow_versions(role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    definition = wf.get("definition")
    if not definition:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workflow definition missing")
    try:
        definition = validate_definition(definition)
    except WorkflowValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message) from e
    version = get_next_workflow_version_number(client, org_id, str(workflow_id), environment_name)
    created = create_workflow_version(
        client,
        org_id=org_id,
        workflow_id=str(workflow_id),
        environment_name=environment_name,
        version=version,
        definition=definition,
        schema_version=wf.get("schema_version") or definition.get("schema_version") or SCHEMA_VERSION,
        created_by=current_user["user_id"],
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="workflow.version.created",
        resource_type="workflow_version",
        resource_id=str(created["id"]),
        metadata={
            "workflow_id": str(workflow_id),
            "version": version,
            "environment": environment_name,
        },
    )
    return {
        "id": str(created["id"]),
        "version": int(created["version"]),
        "created_at": created["created_at"],
        "created_by": str(created["created_by"]) if created.get("created_by") else None,
        "schema_version": created["schema_version"],
    }


@router.get("/{workflow_id}/versions", response_model=WorkflowVersionListResponse)
async def list_workflow_versions_route(
    workflow_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkflowVersionListResponse:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "versioning")
    versions = list_workflow_versions(client, org_id, str(workflow_id), environment_name)
    return WorkflowVersionListResponse(
        versions=[
            WorkflowVersionItem(
                id=str(v["id"]),
                version=int(v["version"]),
                created_at=v["created_at"],
                created_by=str(v["created_by"]) if v.get("created_by") else None,
                schema_version=v.get("schema_version") or "",
            )
            for v in versions
        ]
    )


@router.post("/{workflow_id}/versions/{version_id}/activate")
async def activate_workflow_version_route(
    workflow_id: UUID,
    version_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "versioning")
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as e:
        logger.error("activate_role_failure org_id=%s user_id=%s error=%s stop_condition", org_id, current_user["user_id"], e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from e
    if not can_activate_workflow_version(role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    version = get_workflow_version(client, org_id, str(workflow_id), environment_name, str(version_id))
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    set_active_workflow_version(
        client,
        org_id=org_id,
        workflow_id=str(workflow_id),
        environment_name=environment_name,
        version_id=str(version_id),
        updated_by=current_user["user_id"],
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="workflow.version.activated",
        resource_type="workflow_version",
        resource_id=str(version_id),
        metadata={
            "workflow_id": str(workflow_id),
            "version": int(version.get("version") or 0),
            "environment": environment_name,
        },
    )
    return {
        "active_version_id": str(version_id),
        "version": int(version.get("version") or 0),
    }


@router.get("/{workflow_id}/active", response_model=WorkflowActiveVersion)
async def get_active_workflow_version_route(
    workflow_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkflowActiveVersion:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "versioning")
    active = get_active_workflow_version(client, org_id, str(workflow_id), environment_name)
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active version not found")
    return WorkflowActiveVersion(
        id=str(active["id"]),
        version=int(active["version"]),
        created_at=active["created_at"],
        created_by=str(active["created_by"]) if active.get("created_by") else None,
        schema_version=active.get("schema_version") or "",
        definition=active.get("definition") or {},
    )


@router.post("/{workflow_id}/versions/{version_id}/promote")
async def promote_workflow_version_route(
    workflow_id: UUID,
    version_id: UUID,
    body: PromoteVersionRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    to_env = (body.to_environment or "").strip()
    if not to_env:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="to_environment required")
    if to_env == environment_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target environment must differ")
    if to_env not in {"staging", "production"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target environment")
    client = get_supabase_client(settings)
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as e:
        logger.error("promote_role_failure org_id=%s user_id=%s error=%s stop_condition", org_id, current_user["user_id"], e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from e
    if not can_promote_workflow_version(role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    source_version = get_workflow_version(client, org_id, str(workflow_id), environment_name, str(version_id))
    if not source_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    next_version = get_next_workflow_version_number(client, org_id, str(workflow_id), to_env)
    created = create_workflow_version(
        client,
        org_id=org_id,
        workflow_id=str(workflow_id),
        environment_name=to_env,
        version=next_version,
        definition=source_version.get("definition") or {},
        schema_version=source_version.get("schema_version") or "",
        created_by=current_user["user_id"],
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="workflow.version.promoted",
        resource_type="workflow_version",
        resource_id=str(created["id"]),
        metadata={
            "workflow_id": str(workflow_id),
            "from_env": environment_name,
            "to_env": to_env,
            "source_version_id": str(version_id),
            "target_version_id": str(created["id"]),
        },
    )
    return {
        "source_version_id": str(version_id),
        "target_version_id": str(created["id"]),
        "version": int(created["version"]),
        "environment": to_env,
    }


@router.post("/execute")
async def execute_workflow(
    body: ExecuteRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Create execute run. Approval required if policy requires it; else run immediately."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    start = time.perf_counter()
    workflow_id = str(body.workflow_id)
    client = get_supabase_client(settings)
    plan = get_plan_for_org(client, org_id)
    wf = get_workflow_def(client, org_id, workflow_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    active = get_active_workflow_version(client, org_id, workflow_id, environment_name)
    if not active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active workflow version. Create and activate a version first.",
        )
    definition = active.get("definition")
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active workflow definition missing",
        )
    workflow_version_id = str(active["id"])
    try:
        definition = validate_definition(definition)
    except WorkflowValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message) from e
    try:
        validate_execute_steps(definition)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    parameters = validate_parameters(body.parameters)
    schema_version = active.get("schema_version") or definition.get("schema_version") or SCHEMA_VERSION
    run_hash = compute_run_hash(definition, parameters, schema_version)

    # Policy resolution
    try:
        required_approvals, approver_roles = resolve_policy(client, org_id, workflow_id, "execute")
    except PolicyResolutionError as e:
        logger.error("policy_resolution_failure org_id=%s workflow_id=%s error=%s stop_condition", org_id, workflow_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Policy resolution failed",
        ) from e
    if required_approvals > 0:
        require_feature(plan, "approvals")

    # Role validation (stop condition if invalid)
    try:
        get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as e:
        logger.error("role_validation_failure org_id=%s user_id=%s error=%s stop_condition", org_id, current_user["user_id"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role validation failed",
        ) from e

    # Concurrency check
    active_run_id = check_concurrency(client, org_id, workflow_id, environment_name=environment_name)
    if active_run_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Workflow already has an active run", "active_run_id": active_run_id},
        )

    allowed_envs = [e.strip() for e in (settings.policy_allowed_envs or "").split(",") if e.strip()]
    max_steps = settings.policy_max_steps if settings.policy_max_steps > 0 else None
    max_runtime = settings.policy_max_runtime_seconds if settings.policy_max_runtime_seconds > 0 else None
    decision = evaluate_policy(
        PolicyContext(
            settings=settings,
            org_id=org_id,
            workflow_id=workflow_id,
            definition=definition,
            required_approvals=required_approvals,
            approver_roles=approver_roles,
            environment_name=environment_name,
            max_steps=max_steps,
            max_runtime_seconds=max_runtime,
            allowed_envs=allowed_envs or None,
            allowed_connector_types=None,
        )
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=decision.status_code or status.HTTP_400_BAD_REQUEST,
            detail=decision.message or "Policy denied",
        )
    required_approvals = decision.required_approvals
    approver_roles = decision.approver_roles
    approval_floor_applied = decision.approval_floor_applied

    approval_required = required_approvals > 0
    if approval_required:
        try:
            run = create_execute_run(
                client=client,
                org_id=org_id,
                workflow_id=workflow_id,
                triggered_by=current_user["user_id"],
                definition_snapshot=definition,
                parameters=parameters,
                run_hash=run_hash,
                status=RUN_STATUS_PENDING_APPROVAL,
                approval_status="pending_approval",
                required_approvals=required_approvals,
                approver_roles=approver_roles,
                environment_name=environment_name,
                workflow_version_id=workflow_version_id,
            )
        except Exception:
            active_run_id = check_concurrency(client, org_id, workflow_id, environment_name=environment_name)
            if active_run_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"detail": "Workflow already has an active run", "active_run_id": active_run_id},
                )
            raise
        run_id = str(run["id"])
        _record_workflow_run_usage(client, org_id, environment_name, plan)
        if approval_floor_applied:
            write_audit_event(
                client,
                org_id=org_id,
                actor_id=current_user["user_id"],
                action="policy.override.approval_floor_applied",
                resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                resource_id=run_id,
                metadata={"workflow_id": workflow_id, "forced_required_approvals": 1},
            )
        steps_def = definition.get("steps", [])
        for idx, sdef in enumerate(steps_def):
            create_step(
                client=client,
                run_id=run_id,
                org_id=org_id,
                step_id=sdef["id"],
                step_index=idx,
                step_name=sdef["name"],
                step_type=sdef["type"],
            )
        emit_execute_created(client, org_id, current_user["user_id"], run_id, workflow_id)
        emit_execute_pending_approval(client, org_id, current_user["user_id"], run_id, workflow_id)
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "workflow_execute_created request_id=%s org_id=%s workflow_id=%s run_id=%s latency_ms=%s status=pending_approval",
            request_id_ctx.get(), org_id, workflow_id, run_id, latency_ms,
        )
        return {
            "run_id": run_id,
            "status": RUN_STATUS_PENDING_APPROVAL,
            "approval_status": "pending_approval",
            "approval_required": True,
            "required_approvals": required_approvals,
            "approvals_received": 0,
        }
    else:
        try:
            run = create_execute_run(
                client=client,
                org_id=org_id,
                workflow_id=workflow_id,
                triggered_by=current_user["user_id"],
                definition_snapshot=definition,
                parameters=parameters,
                run_hash=run_hash,
                status=RUN_STATUS_RUNNING,
                approval_status="approved",
                required_approvals=0,
                approver_roles=[],
                environment_name=environment_name,
                workflow_version_id=workflow_version_id,
            )
        except Exception:
            active_run_id = check_concurrency(client, org_id, workflow_id, environment_name=environment_name)
            if active_run_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"detail": "Workflow already has an active run", "active_run_id": active_run_id},
                )
            raise
        run_id = str(run["id"])
        _record_workflow_run_usage(client, org_id, environment_name, plan)
        emit_execute_created(client, org_id, current_user["user_id"], run_id, workflow_id)
        emit_execute_started(client, org_id, current_user["user_id"], run_id)
        final_status, step_rows, errors, rate_limited = execute_workflow_steps(
            settings=settings,
            org_id=org_id,
            user_id=current_user["user_id"],
            run_id=run_id,
            definition=definition,
            parameters=parameters,
            client=client,
            environment_name=environment_name,
        )
        if rate_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        rag_failed = any(s.get("error_code") == ERROR_CODE_RAG_UNAVAILABLE for s in step_rows)
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "workflow_execute request_id=%s org_id=%s workflow_id=%s run_id=%s latency_ms=%s step_count=%s status=%s",
            request_id_ctx.get(), org_id, workflow_id, run_id, latency_ms, len(step_rows), final_status,
        )
        if rag_failed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Retrieval temporarily unavailable",
            )
        return {
            "run_id": run_id,
            "status": final_status,
            "approval_required": False,
            "steps": [_step_to_out(s) for s in step_rows],
            "errors": errors,
        }


def _execute_workflow_with_context(
    *,
    client,
    settings: Settings,
    org_id: str,
    environment_name: str,
    workflow_id: str,
    parameters: dict,
    actor_id: str,
    trigger_type: str,
    schedule_id: str | None = None,
    rollback_of_run_id: str | None = None,
) -> dict:
    start = time.perf_counter()
    plan = get_plan_for_org(client, org_id)
    wf = get_workflow_def(client, org_id, workflow_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    active = get_active_workflow_version(client, org_id, workflow_id, environment_name)
    if not active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active workflow version. Create and activate a version first.",
        )
    definition = active.get("definition")
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active workflow definition missing",
        )
    workflow_version_id = str(active["id"])
    try:
        definition = validate_definition(definition)
    except WorkflowValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message) from e
    try:
        validate_execute_steps(definition)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    parameters = validate_parameters(parameters)
    schema_version = active.get("schema_version") or definition.get("schema_version") or SCHEMA_VERSION
    run_hash = compute_run_hash(definition, parameters, schema_version)

    try:
        required_approvals, approver_roles = resolve_policy(client, org_id, workflow_id, "execute")
    except PolicyResolutionError as e:
        logger.error("policy_resolution_failure org_id=%s workflow_id=%s error=%s stop_condition", org_id, workflow_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Policy resolution failed",
        ) from e
    if required_approvals > 0:
        require_feature(plan, "approvals")

    try:
        get_user_role(client, org_id, actor_id)
    except PolicyResolutionError as e:
        logger.error("role_validation_failure org_id=%s user_id=%s error=%s stop_condition", org_id, actor_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role validation failed",
        ) from e

    active_run_id = check_concurrency(client, org_id, workflow_id, environment_name=environment_name)
    if active_run_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Workflow already has an active run", "active_run_id": active_run_id},
        )

    allowed_envs = [e.strip() for e in (settings.policy_allowed_envs or "").split(",") if e.strip()]
    max_steps = settings.policy_max_steps if settings.policy_max_steps > 0 else None
    max_runtime = settings.policy_max_runtime_seconds if settings.policy_max_runtime_seconds > 0 else None
    decision = evaluate_policy(
        PolicyContext(
            settings=settings,
            org_id=org_id,
            workflow_id=workflow_id,
            definition=definition,
            required_approvals=required_approvals,
            approver_roles=approver_roles,
            environment_name=environment_name,
            max_steps=max_steps,
            max_runtime_seconds=max_runtime,
            allowed_envs=allowed_envs or None,
            allowed_connector_types=None,
        )
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=decision.status_code or status.HTTP_400_BAD_REQUEST,
            detail=decision.message or "Policy denied",
        )
    required_approvals = decision.required_approvals
    approver_roles = decision.approver_roles
    approval_floor_applied = decision.approval_floor_applied

    approval_required = required_approvals > 0
    if approval_required:
        try:
            run = create_execute_run(
                client=client,
                org_id=org_id,
                workflow_id=workflow_id,
                triggered_by=actor_id,
                definition_snapshot=definition,
                parameters=parameters,
                run_hash=run_hash,
                status=RUN_STATUS_PENDING_APPROVAL,
                approval_status="pending_approval",
                required_approvals=required_approvals,
                approver_roles=approver_roles,
                environment_name=environment_name,
                workflow_version_id=workflow_version_id,
                trigger_type=trigger_type,
                schedule_id=schedule_id,
                rollback_of_run_id=rollback_of_run_id,
            )
        except Exception:
            active_run_id = check_concurrency(client, org_id, workflow_id, environment_name=environment_name)
            if active_run_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"detail": "Workflow already has an active run", "active_run_id": active_run_id},
                )
            raise
        run_id = str(run["id"])
        _record_workflow_run_usage(client, org_id, environment_name, plan)
        if approval_floor_applied:
            write_audit_event(
                client,
                org_id=org_id,
                actor_id=actor_id,
                action="policy.override.approval_floor_applied",
                resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                resource_id=run_id,
                metadata={"workflow_id": workflow_id, "forced_required_approvals": 1},
            )
        steps_def = definition.get("steps", [])
        for idx, sdef in enumerate(steps_def):
            create_step(
                client=client,
                run_id=run_id,
                org_id=org_id,
                step_id=sdef["id"],
                step_index=idx,
                step_name=sdef["name"],
                step_type=sdef["type"],
            )
        emit_execute_created(client, org_id, actor_id, run_id, workflow_id)
        emit_execute_pending_approval(client, org_id, actor_id, run_id, workflow_id)
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "workflow_execute_created request_id=%s org_id=%s workflow_id=%s run_id=%s latency_ms=%s status=pending_approval",
            request_id_ctx.get(), org_id, workflow_id, run_id, latency_ms,
        )
        return {
            "run_id": run_id,
            "status": RUN_STATUS_PENDING_APPROVAL,
            "approval_status": "pending_approval",
            "approval_required": True,
            "required_approvals": required_approvals,
            "approvals_received": 0,
        }
    else:
        try:
            run = create_execute_run(
                client=client,
                org_id=org_id,
                workflow_id=workflow_id,
                triggered_by=actor_id,
                definition_snapshot=definition,
                parameters=parameters,
                run_hash=run_hash,
                status=RUN_STATUS_RUNNING,
                approval_status="approved",
                required_approvals=0,
                approver_roles=[],
                environment_name=environment_name,
                workflow_version_id=workflow_version_id,
                trigger_type=trigger_type,
                schedule_id=schedule_id,
                rollback_of_run_id=rollback_of_run_id,
            )
        except Exception:
            active_run_id = check_concurrency(client, org_id, workflow_id, environment_name=environment_name)
            if active_run_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"detail": "Workflow already has an active run", "active_run_id": active_run_id},
                )
            raise
        run_id = str(run["id"])
        _record_workflow_run_usage(client, org_id, environment_name, plan)
        emit_execute_created(client, org_id, actor_id, run_id, workflow_id)
        emit_execute_started(client, org_id, actor_id, run_id)
        final_status, step_rows, errors, rate_limited = execute_workflow_steps(
            settings=settings,
            org_id=org_id,
            user_id=actor_id,
            run_id=run_id,
            definition=definition,
            parameters=parameters,
            client=client,
            environment_name=environment_name,
        )
        if rate_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        rag_failed = any(s.get("error_code") == ERROR_CODE_RAG_UNAVAILABLE for s in step_rows)
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "workflow_execute request_id=%s org_id=%s workflow_id=%s run_id=%s latency_ms=%s step_count=%s status=%s",
            request_id_ctx.get(), org_id, workflow_id, run_id, latency_ms, len(step_rows), final_status,
        )
        if rag_failed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Retrieval temporarily unavailable",
            )
        return {
            "run_id": run_id,
            "status": final_status,
            "approval_required": False,
            "steps": [_step_to_out(s) for s in step_rows],
            "errors": errors,
        }


@router.get("/{workflow_id}/schedules")
async def list_workflow_schedules_route(
    workflow_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    items = list_workflow_schedules(client, org_id, str(workflow_id), environment_name)
    return {
        "schedules": [
            {
                "id": str(s["id"]),
                "workflow_id": str(s["workflow_id"]),
                "cronExpression": s.get("cron_expression") or "",
                "isEnabled": bool(s.get("is_enabled", s.get("enabled", True))),
                "nextRunAt": s.get("next_run_at"),
                "lastRunAt": s.get("last_run_at"),
                "createdAt": s.get("created_at"),
                "updatedAt": s.get("updated_at"),
            }
            for s in items
        ]
    }


@router.post("/{workflow_id}/schedules", status_code=status.HTTP_201_CREATED)
async def create_workflow_schedule_route(
    workflow_id: UUID,
    body: ScheduleCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    wf = get_workflow_def(client, org_id, str(workflow_id))
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    cron_value = body.cron_expression or body.cronExpression
    if not cron_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cron_expression required")
    enabled_value = body.is_enabled if body.is_enabled is not None else body.enabled
    if enabled_value is None:
        enabled_value = True
    next_run_at = compute_next_run_at(cron_value)
    if next_run_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported cron expression")
    created = create_workflow_schedule(
        client,
        org_id=org_id,
        workflow_id=str(workflow_id),
        cron_expression=cron_value,
        environment_name=environment_name,
        enabled=enabled_value,
        next_run_at=next_run_at if enabled_value else None,
        created_by=_user["user_id"],
    )
    return {
        "id": str(created["id"]),
        "workflow_id": str(created["workflow_id"]),
        "cronExpression": created.get("cron_expression") or "",
        "isEnabled": bool(created.get("is_enabled", created.get("enabled", True))),
        "nextRunAt": created.get("next_run_at"),
        "lastRunAt": created.get("last_run_at"),
        "createdAt": created.get("created_at"),
        "updatedAt": created.get("updated_at"),
    }


@router.patch("/schedules/{schedule_id}")
async def update_workflow_schedule_route(
    schedule_id: UUID,
    body: ScheduleUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    schedule = get_workflow_schedule(client, org_id, str(schedule_id), environment_name)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    cron_expression = body.cron_expression or body.cronExpression or schedule.get("cron_expression")
    next_run_at = schedule.get("next_run_at")
    if body.cron_expression is not None:
        next_run_at = compute_next_run_at(body.cron_expression)
        if next_run_at is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported cron expression")
    enabled_value = body.is_enabled if body.is_enabled is not None else body.enabled
    if enabled_value is False:
        next_run_at = None
    elif enabled_value is True and next_run_at is None and cron_expression:
        next_run_at = compute_next_run_at(cron_expression)
    updated = update_workflow_schedule(
        client,
        org_id=org_id,
        schedule_id=str(schedule_id),
        environment_name=environment_name,
        cron_expression=cron_expression,
        enabled=enabled_value,
        next_run_at=next_run_at,
        updated_by=_user["user_id"],
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return {
        "id": str(updated["id"]),
        "workflow_id": str(updated["workflow_id"]),
        "cronExpression": updated.get("cron_expression") or "",
        "isEnabled": bool(updated.get("is_enabled", updated.get("enabled", True))),
        "nextRunAt": updated.get("next_run_at"),
        "lastRunAt": updated.get("last_run_at"),
        "createdAt": updated.get("created_at"),
        "updatedAt": updated.get("updated_at"),
    }


@router.patch("/{workflow_id}/schedules/{schedule_id}")
async def update_workflow_schedule_alias(
    workflow_id: UUID,
    schedule_id: UUID,
    body: ScheduleUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Alias for schedule updates scoped to workflow."""
    schedule = get_workflow_schedule(
        get_supabase_client(settings),
        _admin[1],
        str(schedule_id),
        environment_name,
    )
    if schedule and str(schedule.get("workflow_id")) != str(workflow_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Schedule does not belong to workflow")
    return await update_workflow_schedule_route(schedule_id, body, _admin, environment_name, settings)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_schedule_route(
    schedule_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    schedule = get_workflow_schedule(client, org_id, str(schedule_id), environment_name)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    removed = delete_workflow_schedule(client, org_id, str(schedule_id), environment_name)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return None


@router.delete("/{workflow_id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_schedule_alias(
    workflow_id: UUID,
    schedule_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    schedule = get_workflow_schedule(
        get_supabase_client(settings),
        _admin[1],
        str(schedule_id),
        environment_name,
    )
    if schedule and str(schedule.get("workflow_id")) != str(workflow_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Schedule does not belong to workflow")
    return await delete_workflow_schedule_route(schedule_id, _admin, environment_name, settings)


@router.post("/schedules/dispatch")
async def dispatch_workflow_schedules(
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    now_iso = datetime.now(timezone.utc).isoformat()
    r = (
        client.table("workflow_schedules")
        .select("*")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("enabled", True)
        .lte("next_run_at", now_iso)
        .execute()
    )
    schedules = list(r.data or [])
    results: list[dict] = []
    for schedule in schedules:
        schedule_id = str(schedule["id"])
        actor_id = schedule.get("created_by") or _user["user_id"]
        try:
            response = _execute_workflow_with_context(
                client=client,
                settings=settings,
                org_id=org_id,
                environment_name=environment_name,
                workflow_id=str(schedule["workflow_id"]),
                parameters={},
                actor_id=actor_id,
                trigger_type="schedule",
                schedule_id=schedule_id,
            )
            next_run_at = compute_next_run_at(schedule.get("cron_expression") or "", datetime.now(timezone.utc))
            update_workflow_schedule(
                client,
                org_id=org_id,
                schedule_id=schedule_id,
                environment_name=environment_name,
                cron_expression=None,
                enabled=True if next_run_at else False,
                next_run_at=next_run_at,
                updated_by=_user["user_id"],
            )
            results.append({"schedule_id": schedule_id, "status": "ok", "run_id": response.get("run_id")})
        except HTTPException as exc:
            results.append({"schedule_id": schedule_id, "status": "error", "detail": exc.detail})
    return {"dispatched": results}


@router.post("/runs/{run_id}/rollback")
async def rollback_run(
    run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    run = get_run_with_steps(client, org_id, str(run_id), environment_name)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    workflow_id = run.get("workflow_id")
    if not workflow_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run missing workflow reference")
    base_params = run.get("parameters") or {}
    rollback_params = {**base_params, "rollback_of": str(run_id)}
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="workflow.execute.rollback_requested",
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=str(run_id),
        metadata={"workflow_id": str(workflow_id)},
    )
    return _execute_workflow_with_context(
        client=client,
        settings=settings,
        org_id=org_id,
        environment_name=environment_name,
        workflow_id=str(workflow_id),
        parameters=rollback_params,
        actor_id=current_user["user_id"],
        trigger_type="rollback",
        rollback_of_run_id=str(run_id),
    )


@router.post("/runs/{run_id}/approve")
async def approve_run(
    run_id: UUID,
    body: ApproveRejectRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Approve a pending execute run. Idempotent if already approved by this user."""
    if settings.disable_execute:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Execute is disabled")
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    run_id_str = str(run_id)
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "approvals")
    run = get_run_with_steps(client, org_id, run_id_str, environment_name)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.get("run_type") != RUN_TYPE_EXECUTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run is not an execute run",
        )
    if run.get("status") != RUN_STATUS_PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run is not pending approval",
        )
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as e:
        logger.error("approve_role_failure org_id=%s user_id=%s error=%s stop_condition", org_id, current_user["user_id"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role validation failed",
        ) from e
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    insert_run_approval(
        client=client,
        run_id=run_id_str,
        org_id=org_id,
        approver_id=current_user["user_id"],
        status="approved",
        comment=body.comment,
    )
    emit_execute_approval_recorded(client, org_id, current_user["user_id"], run_id_str, "approved")
    approved_count, has_rejected = get_approval_counts(client, run_id_str)
    required = run.get("required_approvals") or 1
    if has_rejected:
        update_run(client, run_id_str, status="cancelled", approval_status="rejected")
        emit_execute_rejected(client, org_id, current_user["user_id"], run_id_str)
        emit_execute_cancelled(client, org_id, current_user["user_id"], run_id_str)
        return {
            "run_id": run_id_str,
            "status": "cancelled",
            "approval_status": "rejected",
            "required_approvals": required,
            "approvals_received": approved_count,
            "message": "Run rejected",
        }
    if approved_count >= required:
        definition = run.get("definition_snapshot") or {}
        external_step_types = {"slack_post_message", "email_send", "webhook_post"}
        has_external = any((s.get("type") or "").strip() in external_step_types for s in (definition.get("steps") or []))
        if settings.disable_execute:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Execute is disabled")
        if settings.disable_connectors and has_external:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Connectors are disabled")
        claimed = try_mark_run_running(client, run_id_str, org_id)
        if not claimed:
            latest = get_run_with_steps(client, org_id, run_id_str, environment_name) or run
            return {
                "run_id": run_id_str,
                "status": latest.get("status"),
                "approval_status": latest.get("approval_status"),
                "required_approvals": required,
                "approvals_received": approved_count,
                "message": "Run already started or resolved",
            }
        emit_execute_approved(client, org_id, current_user["user_id"], run_id_str)
        emit_execute_started(client, org_id, current_user["user_id"], run_id_str)
        definition = run.get("definition_snapshot") or {}
        parameters = run.get("parameters") or {}
        run_environment = (run.get("environment") or "default").strip() or "default"
        final_status, step_rows, _, rate_limited = execute_workflow_steps(
            settings=settings,
            org_id=org_id,
            user_id=current_user["user_id"],
            run_id=run_id_str,
            definition=definition,
            parameters=parameters,
            client=client,
            environment_name=run_environment,
            steps_exist=True,
        )
        if rate_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        rag_failed = any(s.get("error_code") == ERROR_CODE_RAG_UNAVAILABLE for s in step_rows)
        if rag_failed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Retrieval temporarily unavailable",
            )
        return {
            "run_id": run_id_str,
            "status": final_status,
            "approval_status": "approved",
            "required_approvals": required,
            "approvals_received": approved_count,
            "steps": [_step_to_out(s) for s in step_rows],
        }
    return {
        "run_id": run_id_str,
        "status": RUN_STATUS_PENDING_APPROVAL,
        "approval_status": "pending_approval",
        "required_approvals": required,
        "approvals_received": approved_count,
        "message": "Approval recorded",
    }


@router.post("/runs/{run_id}/reject")
async def reject_run(
    run_id: UUID,
    body: ApproveRejectRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Reject a pending execute run."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    run_id_str = str(run_id)
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "approvals")
    run = get_run_with_steps(client, org_id, run_id_str, environment_name)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.get("run_type") != RUN_TYPE_EXECUTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run is not an execute run",
        )
    if run.get("status") != RUN_STATUS_PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run is not pending approval",
        )
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as e:
        logger.error("reject_role_failure org_id=%s user_id=%s error=%s stop_condition", org_id, current_user["user_id"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role validation failed",
        ) from e
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    existing = (
        client.table("run_approvals")
        .select("status")
        .eq("run_id", run_id_str)
        .eq("approver_id", current_user["user_id"])
        .limit(1)
        .execute()
    )
    if existing.data and len(existing.data) > 0 and existing.data[0].get("status") == "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject; you have already approved this run",
        )
    insert_run_approval(
        client=client,
        run_id=run_id_str,
        org_id=org_id,
        approver_id=current_user["user_id"],
        status="rejected",
        comment=body.comment,
    )
    update_run(client, run_id_str, status="cancelled", approval_status="rejected")
    emit_execute_rejected(client, org_id, current_user["user_id"], run_id_str)
    emit_execute_cancelled(client, org_id, current_user["user_id"], run_id_str)
    return {
        "run_id": run_id_str,
        "status": "cancelled",
        "approval_status": "rejected",
        "message": "Run rejected",
    }


@router.get("/approvals/pending")
async def list_pending_approvals(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """List pending execute approvals for org + environment."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "versioning")
    r = (
        client.table("workflow_runs")
        .select("id, workflow_id, created_at, required_approvals")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("run_type", RUN_TYPE_EXECUTE)
        .eq("status", RUN_STATUS_PENDING_APPROVAL)
        .eq("approval_status", RUN_STATUS_PENDING_APPROVAL)
        .order("created_at", desc=True)
        .execute()
    )
    runs = list(r.data or [])
    workflow_ids = [str(run["workflow_id"]) for run in runs if run.get("workflow_id")]
    workflow_names: dict[str, str] = {}
    if workflow_ids:
        wf = (
            client.table("workflow_defs")
            .select("id, name")
            .eq("org_id", org_id)
            .in_("id", workflow_ids)
            .execute()
        )
        workflow_names = {str(w["id"]): w.get("name") or "" for w in (wf.data or [])}
    items = []
    for run in runs:
        run_id = str(run["id"])
        approved_count, _ = get_approval_counts(client, run_id)
        items.append(
            {
                "run_id": run_id,
                "workflow_id": str(run["workflow_id"]) if run.get("workflow_id") else None,
                "workflow_name": workflow_names.get(str(run.get("workflow_id")) or "", "") or None,
                "created_at": run.get("created_at"),
                "required_approvals": run.get("required_approvals") or 0,
                "approvals_received": approved_count,
            }
        )
    return {"items": items}


@approvals_router.get("/pending")
async def list_pending_approvals_alias(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "approvals")
    return await list_pending_approvals(_user, org_id, environment_name, settings)


@approvals_router.get("")
async def list_approvals_alias(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    type: str | None = Query(default=None),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "approvals")
    q = (
        client.table("workflow_runs")
        .select("id, workflow_id, created_at, required_approvals, approval_status, triggered_by")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("run_type", RUN_TYPE_EXECUTE)
        .order("created_at", desc=True)
    )
    if status:
        q = q.eq("approval_status", status)
    else:
        q = q.eq("approval_status", RUN_STATUS_PENDING_APPROVAL)
    runs = list(q.execute().data or [])
    workflow_ids = [str(run["workflow_id"]) for run in runs if run.get("workflow_id")]
    workflow_names: dict[str, str] = {}
    if workflow_ids:
        wf = (
            client.table("workflow_defs")
            .select("id, name")
            .eq("org_id", org_id)
            .in_("id", workflow_ids)
            .execute()
        )
        workflow_names = {str(w["id"]): w.get("name") or "" for w in (wf.data or [])}
    approvals = []
    for run in runs:
        required = run.get("required_approvals") or 0
        pri = "high" if required >= 2 else "medium"
        if priority and pri != priority:
            continue
        if type and type != "workflow":
            continue
        approvals.append(
            {
                "id": str(run["id"]),
                "title": workflow_names.get(str(run.get("workflow_id")), "Workflow approval"),
                "description": "Workflow execution approval",
                "type": "workflow",
                "priority": pri,
                "status": run.get("approval_status") or "pending",
                "gate_type": "execute",
                "requested_by": run.get("triggered_by"),
                "requested_at": run.get("created_at"),
                "reviewed_by": None,
                "reviewed_at": None,
                "context": {"workflow_id": str(run.get("workflow_id")) if run.get("workflow_id") else None},
                "environment": environment_name,
            }
        )
    approvals.sort(key=lambda item: item["requested_at"] or "", reverse=True)
    approvals.sort(key=lambda item: 0 if item["priority"] == "high" else 1)
    return {"approvals": approvals}


@approvals_router.post("/{run_id}/approve")
async def approve_run_alias(
    run_id: UUID,
    body: ApproveRejectRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "approvals")
    return await approve_run(run_id, body, current_user, org_id, settings)


@approvals_router.post("/{run_id}/reject")
async def reject_run_alias(
    run_id: UUID,
    body: ApproveRejectRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    require_feature(get_plan_for_org(client, org_id), "approvals")
    return await reject_run(run_id, body, current_user, org_id, settings)


@router.get("/runs")
async def list_runs(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    status: str | None = Query(default=None),
    approval_status: str | None = Query(default=None),
    workflow_id: UUID | None = Query(default=None),
    run_type: str | None = Query(default=None),
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict:
    """List workflow runs for org + environment with filters."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    q = (
        client.table("workflow_runs")
        .select(
            "id, workflow_id, run_type, status, approval_status, required_approvals, created_at, completed_at, environment, triggered_by, trigger_type, schedule_id, rollback_of_run_id"
        )
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status:
        q = q.eq("status", status)
    if approval_status:
        q = q.eq("approval_status", approval_status)
    if workflow_id:
        q = q.eq("workflow_id", str(workflow_id))
    if run_type:
        q = q.eq("run_type", run_type)
    if start_at:
        q = q.gte("created_at", start_at)
    if end_at:
        q = q.lte("created_at", end_at)
    r = q.execute()
    runs = list(r.data or [])
    workflow_ids = list({str(run["workflow_id"]) for run in runs if run.get("workflow_id")})
    workflow_names: dict[str, str] = {}
    if workflow_ids:
        wf = (
            client.table("workflow_defs")
            .select("id, name")
            .eq("org_id", org_id)
            .in_("id", workflow_ids)
            .execute()
        )
        workflow_names = {str(w["id"]): w.get("name") or "" for w in (wf.data or [])}
    items = []
    for run in runs:
        workflow_id_value = str(run["workflow_id"]) if run.get("workflow_id") else None
        items.append(
            {
                "id": str(run["id"]),
                "workflow_id": workflow_id_value,
                "workflow_name": workflow_names.get(workflow_id_value or "", "") or None,
                "run_type": run.get("run_type"),
                "status": run.get("status"),
                "approval_status": run.get("approval_status"),
                "trigger_type": run.get("trigger_type"),
                "schedule_id": str(run.get("schedule_id")) if run.get("schedule_id") else None,
                "rollback_of_run_id": str(run.get("rollback_of_run_id")) if run.get("rollback_of_run_id") else None,
                "required_approvals": run.get("required_approvals") or 0,
                "created_at": run.get("created_at"),
                "completed_at": run.get("completed_at"),
                "environment": run.get("environment"),
                "triggered_by": run.get("triggered_by"),
            }
        )
    return {"runs": items}


@router.get("/runs/{run_id}")
async def get_run(
    run_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Get run with steps. Org-scoped. BE-20: includes approval fields."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    run_id_str = str(run_id)
    client = get_supabase_client(settings)
    run = get_run_with_steps(client, org_id, run_id_str, environment_name)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    steps = run.pop("steps", [])
    required = run.get("required_approvals")
    approval_required = (required or 0) > 0
    approved_count, _ = get_approval_counts(client, run_id_str)
    run_out = {
        "id": str(run["id"]),
        "workflowId": str(run.get("workflow_id")) if run.get("workflow_id") else None,
        "status": run.get("status"),
        "approvalStatus": run.get("approval_status") or "not_required",
        "environment": run.get("environment") or environment_name,
        "startedAt": run.get("started_at") or run.get("created_at"),
        "completedAt": run.get("completed_at"),
        "durationMs": run.get("duration_ms"),
        "triggeredBy": run.get("triggered_by"),
        "errorMessage": run.get("error_message"),
        "approvalRequired": approval_required,
        "requiredApprovals": required,
        "approvalsReceived": approved_count,
    }
    return {"run": run_out, "steps": [_run_step_out(s) for s in steps]}


@runs_router.get("")
async def list_runs_alias(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    status: str | None = Query(default=None),
    approval_status: str | None = Query(default=None, alias="approvalStatus"),
    workflow_id: UUID | None = Query(default=None, alias="workflowId"),
    run_type: str | None = Query(default=None),
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="dateFrom"),
    date_to: str | None = Query(default=None, alias="dateTo"),
    environment: str | None = Query(default=None),
    page: int | None = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    if environment and environment != environment_name:
        return {"runs": [], "total": 0}
    client = get_supabase_client(settings)
    q = (
        client.table("workflow_runs")
        .select(
            "id, workflow_id, run_type, status, approval_status, required_approvals, "
            "created_at, started_at, completed_at, duration_ms, error_message, "
            "environment, triggered_by, trigger_type, schedule_id, rollback_of_run_id"
        )
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .order("created_at", desc=True)
    )
    if status:
        q = q.eq("status", status)
    if approval_status:
        q = q.eq("approval_status", approval_status)
    if workflow_id:
        q = q.eq("workflow_id", str(workflow_id))
    if run_type:
        q = q.eq("run_type", run_type)
    if start_at or date_from:
        q = q.gte("created_at", start_at or date_from)
    if end_at or date_to:
        q = q.lte("created_at", end_at or date_to)
    total_rows = q.execute().data or []
    total = len(total_rows)
    offset = ((page or 1) - 1) * limit
    rows = total_rows[offset : offset + limit]
    workflow_ids = list({str(run["workflow_id"]) for run in rows if run.get("workflow_id")})
    workflow_names: dict[str, str] = {}
    if workflow_ids:
        wf = (
            client.table("workflow_defs")
            .select("id, name")
            .eq("org_id", org_id)
            .in_("id", workflow_ids)
            .execute()
        )
        workflow_names = {str(w["id"]): w.get("name") or "" for w in (wf.data or [])}
    items = []
    for run in rows:
        workflow_id_value = str(run["workflow_id"]) if run.get("workflow_id") else None
        items.append(
            {
                "id": str(run["id"]),
                "workflowId": workflow_id_value,
                "workflowName": workflow_names.get(workflow_id_value or "", "") or None,
                "status": run.get("status"),
                "approvalStatus": run.get("approval_status") or "not_required",
                "environment": run.get("environment") or environment_name,
                "startedAt": run.get("started_at") or run.get("created_at"),
                "completedAt": run.get("completed_at"),
                "durationMs": run.get("duration_ms"),
                "triggeredBy": run.get("triggered_by"),
                "errorMessage": run.get("error_message"),
            }
        )
    return {"runs": items, "total": total}


@runs_router.get("/{run_id}")
async def get_run_alias(
    run_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await get_run(run_id, _user, org_id, environment_name, settings)


@runs_router.post("/{run_id}/retry")
async def retry_run_alias(
    run_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    run = (
        client.table("workflow_runs")
        .select("id, status")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(run_id))
        .limit(1)
        .execute()
        .data
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    client.table("workflow_runs").update(
        {"status": "running", "error_message": None}
    ).eq("id", str(run_id)).eq("org_id", org_id).execute()
    return {"success": True}


@runs_router.post("/{run_id}/cancel")
async def cancel_run_alias(
    run_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    run = (
        client.table("workflow_runs")
        .select("id, status")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("id", str(run_id))
        .limit(1)
        .execute()
        .data
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    client.table("workflow_runs").update(
        {"status": "failed", "error_message": "Cancelled"}
    ).eq("id", str(run_id)).eq("org_id", org_id).execute()
    return {"success": True}


@runs_router.post("/{run_id}/rollback")
async def rollback_run_alias(
    run_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await rollback_run(run_id, _admin, environment_name, settings)


@router.get("")
async def list_workflows_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """List workflows for org."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    workflows = list_workflows(client, org_id)
    workflow_ids = [str(w["id"]) for w in workflows if w.get("id")]
    counts: dict[str, int] = {}
    success_counts: dict[str, int] = {}
    last_runs: dict[str, str] = {}
    if workflow_ids:
        r = (
            client.table("workflow_runs")
            .select("workflow_id, status, created_at")
            .eq("org_id", org_id)
            .eq("environment", environment_name)
            .in_("workflow_id", workflow_ids)
            .execute()
        )
        for row in list(r.data or []):
            key = str(row.get("workflow_id"))
            counts[key] = counts.get(key, 0) + 1
            if row.get("status") == "completed":
                success_counts[key] = success_counts.get(key, 0) + 1
            created_at = row.get("created_at")
            if created_at and key not in last_runs:
                last_runs[key] = created_at
    return {
        "workflows": [
            {
                "id": str(w["id"]),
                "name": w["name"],
                "goal": w.get("goal") or _generate_goal(w.get("name") or "", w.get("description")),
                "description": w.get("description"),
                "status": w.get("status") or "draft",
                "stage": w.get("stage") or "build",
                "version": w.get("version") or "v1.0.0",
                "schema_version": w["schema_version"],
                "updated_at": w["updated_at"],
                "runCount": w.get("run_count") or counts.get(str(w["id"]), 0),
                "successRate": float(w.get("success_rate") or 0)
                if w.get("success_rate") is not None
                else (
                    round(
                        (success_counts.get(str(w["id"]), 0) / counts.get(str(w["id"]), 1)) * 100,
                        2,
                    )
                    if counts.get(str(w["id"]), 0)
                    else 0
                ),
                "lastRun": w.get("last_run_at") or last_runs.get(str(w["id"])),
                "nextRunAt": w.get("next_run_at"),
                "environment": environment_name,
            }
            for w in workflows
        ],
    }


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Get workflow definition by id. Org-scoped."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    wf = get_workflow_def(client, org_id, str(workflow_id))
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    nodes = list_workflow_nodes(client, org_id, str(workflow_id), environment_name)
    steps = []
    for idx, node in enumerate(nodes):
        config = node.get("config") or {}
        steps.append(
            {
                "id": str(node["id"]),
                "order": node.get("order_index") or idx,
                "type": node.get("node_type") or "",
                "name": node.get("name") or node.get("title") or "",
                "description": node.get("description") or node.get("instruction"),
                "systemIcon": node.get("system_icon"),
                "systemName": node.get("system_name"),
                "status": node.get("status") or "needs_config",
                "hasApprovalGate": bool(node.get("has_approval_gate")),
                "config": {
                    "inputs": node.get("inputs") or config.get("inputs") or [],
                    "outputs": node.get("outputs") or config.get("outputs") or [],
                    "guardrails": node.get("guardrails") or config.get("guardrails") or [],
                },
            }
        )
    prompts = (
        client.table("operator_prompts")
        .select("id, label, prompt")
        .eq("org_id", org_id)
        .eq("is_active", True)
        .order("order_index", desc=False)
        .execute()
        .data
        or []
    )
    return {
        "workflow": {
            "id": str(wf["id"]),
            "name": wf["name"],
            "goal": wf.get("goal") or _generate_goal(wf.get("name") or "", wf.get("description")),
            "description": wf.get("description"),
            "status": wf.get("status") or "draft",
            "stage": wf.get("stage") or "build",
            "environment": environment_name,
            "version": wf.get("version") or "v1.0.0",
            "lastRunAt": wf.get("last_run_at"),
            "nextRunAt": wf.get("next_run_at"),
            "runCount": wf.get("run_count") or 0,
            "successRate": float(wf.get("success_rate") or 0),
        },
        "steps": steps,
        "aiPrompts": [
            {
                "id": str(item["id"]),
                "label": item.get("label") or "",
                "prompt": item.get("prompt") or "",
            }
            for item in prompts
        ],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workflow_route(
    body: WorkflowCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    plan = get_plan_for_org(client, org_id)
    count_result = client.table("workflow_defs").select("id", count="exact").eq("org_id", org_id).execute()
    current_count = count_result.count or 0 if hasattr(count_result, "count") else len(count_result.data or [])
    require_limit(current_count, plan.get("workflows_limit"), "workflows")
    definition = {"schema_version": SCHEMA_VERSION, "steps": []}
    goal = body.goal or _generate_goal(body.name, body.description)
    row = {
        "org_id": org_id,
        "name": body.name.strip(),
        "goal": goal,
        "description": body.description,
        "definition": definition,
        "schema_version": SCHEMA_VERSION,
        "status": "draft",
        "stage": "build",
        "version": "v1.0.0",
        "environment_id": body.environment_id,
        "created_by": _user.get("user_id"),
    }
    r = client.table("workflow_defs").insert(row).execute()
    if not r.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Workflow create failed")
    workflow_id = str(r.data[0]["id"])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="workflow.created",
        resource_type="workflow",
        resource_id=workflow_id,
        metadata={"environment": environment_name},
    )
    return {"id": workflow_id}


@router.patch("/{workflow_id}")
async def update_workflow_route(
    workflow_id: UUID,
    body: WorkflowUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    payload: dict = {}
    if body.name is not None:
        payload["name"] = body.name
    if body.description is not None:
        payload["description"] = body.description
    if body.goal is not None:
        payload["goal"] = body.goal
    if body.status is not None:
        payload["status"] = body.status
    if body.version is not None:
        payload["version"] = body.version
    if not payload:
        return await get_workflow(workflow_id, _admin[0], org_id, environment_name, settings)
    client = get_supabase_client(settings)
    updated = (
        client.table("workflow_defs")
        .update(payload)
        .eq("org_id", org_id)
        .eq("id", str(workflow_id))
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="workflow.updated",
        resource_type="workflow",
        resource_id=str(workflow_id),
        metadata={"environment": environment_name, "fields": list(payload.keys())},
    )
    return await get_workflow(workflow_id, _admin[0], org_id, environment_name, settings)


@router.post("/{workflow_id}/stage")
async def update_workflow_stage(
    workflow_id: UUID,
    body: WorkflowStageUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = get_supabase_client(settings)
    wf = get_workflow_def(client, org_id, str(workflow_id))
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    nodes = list_workflow_nodes(client, org_id, str(workflow_id), environment_name)
    if body.stage == "review":
        if any((n.get("status") or "needs_config") != "configured" for n in nodes):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All steps must be configured")
    if body.stage == "activate":
        if any((n.get("status") or "needs_config") != "configured" for n in nodes):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Review checks not satisfied")
    if body.stage == "run" and (wf.get("status") or "draft") != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workflow must be active to run")
    updated = (
        client.table("workflow_defs")
        .update({"stage": body.stage})
        .eq("org_id", org_id)
        .eq("id", str(workflow_id))
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="workflow.stage.changed",
        resource_type="workflow",
        resource_id=str(workflow_id),
        metadata={"environment": environment_name, "stage": body.stage},
    )
    return {"workflowId": str(workflow_id), "stage": body.stage}


@router.post("/{workflow_id}/ai/improve-step")
async def workflow_ai_improve_step(
    workflow_id: UUID,
    body: WorkflowAiStepRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    node = get_workflow_node(client, org_id, body.step_id, environment_name)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="workflow.ai.improve",
        resource_type="workflow",
        resource_id=str(workflow_id),
        metadata={"environment": environment_name, "step_id": body.step_id},
    )
    response = {
        "suggestions": [
            {
                "type": "improvement",
                "title": "Clarify step inputs",
                "description": "Add explicit inputs and outputs for better reliability.",
                "changes": {"inputs": node.get("inputs") or [], "outputs": node.get("outputs") or []},
            }
        ]
    }
    plan = get_plan_for_org(client, org_id)
    period_start, period_end = get_current_period()
    ai_meta = build_ai_usage_metadata(
        input_texts=[
            node.get("name") or "",
            node.get("description") or node.get("instruction") or "",
        ],
        output_texts=[response["suggestions"][0]["description"]],
        model_name=None,
        source="workflow.ai.improve",
        source_id=str(workflow_id),
    )
    apply_usage_with_overage(
        client=client,
        org_id=org_id,
        environment=environment_name,
        metric_type="ai_credits",
        quantity=int(ai_meta["credits"]),
        plan=plan,
        period_start=period_start,
        period_end=period_end,
        metadata=ai_meta,
    )
    return response


@router.post("/{workflow_id}/ai/explain-step")
async def workflow_ai_explain_step(
    workflow_id: UUID,
    body: WorkflowAiStepRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    node = get_workflow_node(client, org_id, body.step_id, environment_name)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    response = {
        "explanation": f"This step executes {node.get('node_type') or 'an action'} called {node.get('name') or node.get('title')}.",
        "dataFlow": "Inputs are transformed and passed to downstream steps.",
        "potentialIssues": [],
    }
    plan = get_plan_for_org(client, org_id)
    period_start, period_end = get_current_period()
    ai_meta = build_ai_usage_metadata(
        input_texts=[
            node.get("name") or "",
            node.get("description") or node.get("instruction") or "",
        ],
        output_texts=[response["explanation"], response["dataFlow"]],
        model_name=None,
        source="workflow.ai.explain",
        source_id=str(workflow_id),
    )
    apply_usage_with_overage(
        client=client,
        org_id=org_id,
        environment=environment_name,
        metric_type="ai_credits",
        quantity=int(ai_meta["credits"]),
        plan=plan,
        period_start=period_start,
        period_end=period_end,
        metadata=ai_meta,
    )
    return response


@router.post("/{workflow_id}/ai/suggest-next")
async def workflow_ai_suggest_next(
    workflow_id: UUID,
    body: WorkflowAiSuggestRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    _ = body.after_step_id
    response = {
        "suggestions": [
            {
                "type": "connector",
                "name": "Notify stakeholders",
                "description": "Send a Slack message with the results.",
                "reason": "Keeps teams informed after automation completes.",
                "config": {},
            }
        ]
    }
    plan = get_plan_for_org(client, org_id)
    period_start, period_end = get_current_period()
    ai_meta = build_ai_usage_metadata(
        input_texts=[body.after_step_id or ""],
        output_texts=[response["suggestions"][0]["description"]],
        model_name=None,
        source="workflow.ai.suggest",
        source_id=str(workflow_id),
    )
    apply_usage_with_overage(
        client=client,
        org_id=org_id,
        environment=environment_name,
        metric_type="ai_credits",
        quantity=int(ai_meta["credits"]),
        plan=plan,
        period_start=period_start,
        period_end=period_end,
        metadata=ai_meta,
    )
    return response


@router.post("/{workflow_id}/ai/chat")
async def workflow_ai_chat(
    workflow_id: UUID,
    body: WorkflowAiChatRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="workflow.ai.chat",
        resource_type="workflow",
        resource_id=str(workflow_id),
        metadata={"environment": environment_name},
    )
    response = {
        "response": f"Got it. I can help adjust the workflow based on: {body.message}",
        "actions": [],
        "requiresConfirmation": False,
    }
    plan = get_plan_for_org(client, org_id)
    period_start, period_end = get_current_period()
    ai_meta = build_ai_usage_metadata(
        input_texts=[body.message],
        output_texts=[response["response"]],
        model_name=None,
        source="workflow.ai.chat",
        source_id=str(workflow_id),
    )
    apply_usage_with_overage(
        client=client,
        org_id=org_id,
        environment=environment_name,
        metric_type="ai_credits",
        quantity=int(ai_meta["credits"]),
        plan=plan,
        period_start=period_start,
        period_end=period_end,
        metadata=ai_meta,
    )
    return response
