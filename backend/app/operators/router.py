from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.operators.schemas import (
    OperatorActionPlanRequest,
    OperatorActionPlanResponse,
    OperatorCreateRequest,
    OperatorDetail,
    OperatorLinkCreateRequest,
    OperatorLinkListResponse,
    OperatorLinkSummary,
    OperatorListResponse,
    OperatorRunRequest,
    OperatorRunResponse,
    OperatorSessionCreateRequest,
    OperatorSessionDetail,
    OperatorSessionListResponse,
    OperatorUpdateRequest,
    OperatorVersionListResponse,
    OperatorVersionSummary,
)
from app.operators.repository import (
    create_operator,
    create_operator_action,
    create_operator_action_plan,
    create_operator_session,
    create_operator_version,
    get_active_operator_version,
    get_latest_action_plan,
    get_operator,
    get_operator_session,
    get_operator_version,
    get_next_operator_version_number,
    list_connectors_by_ids,
    list_operator_versions,
    list_operator_versions_by_ids,
    list_active_versions,
    list_operator_actions,
    list_operator_bindings,
    list_operator_links,
    list_operator_sessions,
    list_sessions_for_user,
    list_operators,
    create_operator_link,
    delete_operator_link,
    set_operator_connectors,
    set_active_operator_version,
    update_action_plan_status,
    update_operator,
    update_operator_session_status,
)
from app.billing.service import (
    apply_usage_with_overage,
    build_ai_usage_metadata,
    get_current_period,
    get_default_usage_quantity,
    get_plan_for_org,
    record_usage,
    require_limit,
)
from app.operators.services.execution import execute_operator_workflow, resolve_execution_target
from app.operators.services.plans import build_operator_action_plan
from app.workflows.audit import write_audit_event
from app.workflows.policy import PolicyResolutionError, get_user_role

router = APIRouter(prefix="/api/operators", tags=["operators"])
agents_router = APIRouter(prefix="/api/agents", tags=["agents"])
sessions_router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionTaskRequest(BaseModel):
    task: str | None = None
    context: dict | None = None


class SessionExecuteRequest(BaseModel):
    action_ids: list[str] = Field(default_factory=list, alias="actionIds")


class SessionCreateRequest(BaseModel):
    title: str
    context_entity_type: str | None = Field(default=None, alias="contextEntityType")
    context_entity_id: str | None = Field(default=None, alias="contextEntityId")


class AgentCreateRequest(BaseModel):
    name: str
    description: str | None = None
    role: str | None = None
    capabilities: list[str] | None = None
    config: dict | None = None
    environment_id: str | None = Field(default=None, alias="environmentId")
    icon: str | None = None
    avatar_color: str | None = Field(default=None, alias="avatarColor")


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    role: str | None = None
    capabilities: list[str] | None = None
    config: dict | None = None
    status: str | None = None
    icon: str | None = None
    avatar_color: str | None = Field(default=None, alias="avatarColor")


class AgentVersionCreateRequest(BaseModel):
    version_number: str | None = Field(default=None, alias="versionNumber")
    name: str | None = None
    config: dict | None = None


class AgentIconSuggestRequest(BaseModel):
    name: str
    purpose: str | None = None


def _env_allowed(operator: dict, environment: str) -> bool:
    allowed = operator.get("allowed_environments") or []
    if not allowed:
        return True
    return environment in allowed


VALID_AGENT_ICONS = {
    "megaphone",
    "trending-up",
    "database",
    "pie-chart",
    "headphones",
    "bot",
    "brain",
    "zap",
    "users",
    "shield",
    "sparkles",
    "workflow",
}

VALID_AVATAR_COLORS = {
    "bg-emerald-500",
    "bg-blue-500",
    "bg-amber-500",
    "bg-purple-500",
    "bg-rose-500",
    "bg-cyan-500",
}


def _default_avatar_color(role: str | None, status: str | None) -> str:
    status_value = (status or "").lower()
    if status_value == "error":
        return "bg-rose-500"
    if status_value in {"draft", "inactive"}:
        return "bg-amber-500"
    role_value = (role or "").strip()
    mapping = {
        "Orchestrator": "bg-emerald-500",
        "Executor": "bg-blue-500",
        "Analyst": "bg-purple-500",
        "QA": "bg-amber-500",
        "Router": "bg-cyan-500",
    }
    return mapping.get(role_value, "bg-emerald-500")


def _suggest_icon(name: str, purpose: str | None = None) -> tuple[str, float]:
    exact = {
        "Marketing Operator": "megaphone",
        "Sales Assistant": "trending-up",
        "Data Quality Agent": "database",
        "Finance Reporter": "pie-chart",
        "Support Coordinator": "headphones",
    }
    if name in exact:
        return exact[name], 0.95
    text = f"{name} {purpose or ''}".lower()
    if "marketing" in text:
        return "megaphone", 0.9
    if "sales" in text:
        return "trending-up", 0.9
    if "data" in text or "quality" in text:
        return "database", 0.85
    if "finance" in text or "report" in text:
        return "pie-chart", 0.85
    if "support" in text or "customer" in text:
        return "headphones", 0.85
    return "bot", 0.6


def _suggest_color(icon: str) -> str:
    mapping = {
        "megaphone": "bg-emerald-500",
        "trending-up": "bg-blue-500",
        "database": "bg-cyan-500",
        "pie-chart": "bg-purple-500",
        "headphones": "bg-amber-500",
        "bot": "bg-blue-500",
    }
    return mapping.get(icon, "bg-emerald-500")


def _validate_icon(icon: str | None) -> None:
    if icon is None:
        return
    if icon not in VALID_AGENT_ICONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid icon value")


def _validate_avatar_color(value: str | None) -> None:
    if value is None:
        return
    if value not in VALID_AVATAR_COLORS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid avatarColor value")


def _connected_systems(connectors: list[dict]) -> list[str]:
    items: list[str] = []
    for conn in connectors:
        name = conn.get("name") or conn.get("vendor") or conn.get("type") or ""
        if name:
            items.append(name)
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _operator_summary(operator: dict) -> dict:
    name = operator.get("name") or ""
    stored_color = operator.get("avatar_color")
    avatar_color = (
        stored_color
        if stored_color in VALID_AVATAR_COLORS
        else _default_avatar_color(operator.get("role"), operator.get("status"))
    )
    icon_value = operator.get("icon")
    if icon_value not in VALID_AGENT_ICONS:
        icon_value = None
    return {
        "id": str(operator["id"]),
        "name": name,
        "description": operator.get("description"),
        "status": operator.get("status") or "draft",
        "role": operator.get("role"),
        "capabilities": list(operator.get("capabilities") or []),
        "config": operator.get("config") or {},
        "environment": operator.get("environment") or None,
        "totalRuns": operator.get("total_runs") or 0,
        "successRate": float(operator.get("success_rate") or 0),
        "avgDuration": operator.get("avg_duration"),
        "icon": icon_value,
        "avatarColor": avatar_color,
        "allowed_environments": list(operator.get("allowed_environments") or []),
        "requires_admin": bool(operator.get("requires_admin")),
        "requires_approval": bool(operator.get("requires_approval")),
        "approval_roles": list(operator.get("approval_roles") or []),
        "active_version": None,
    }


def _version_summary(version: dict | None) -> dict | None:
    if not version:
        return None
    version_value = version.get("version")
    return {
        "id": str(version["id"]),
        "operator_id": str(version["operator_id"]),
        "environment": version.get("environment") or "",
        "version": int(version_value or 0) if str(version_value or "").isdigit() else (version_value or 0),
        "versionNumber": str(version_value) if version_value is not None else None,
        "name": version.get("name") or "",
        "description": version.get("description"),
        "role": version.get("role"),
        "capabilities": list(version.get("capabilities") or []),
        "config": version.get("config") or {},
        "created_at": version.get("created_at"),
    }


def _operator_detail(operator: dict, connectors: list[dict], active_version: dict | None) -> dict:
    return {
        **_operator_summary(operator),
        "system_prompt": operator.get("system_prompt"),
        "connectors": [
            {
                "id": str(conn["id"]),
                "name": conn.get("name") or "",
                "vendor": conn.get("vendor") or conn.get("type") or "",
                "type": conn.get("type") or "",
                "status": conn.get("status") or "",
                "environment": conn.get("environment") or "",
                "updated_at": conn.get("updated_at"),
                "config": conn.get("config") or {},
            }
            for conn in connectors
        ],
        "connectedSystems": _connected_systems(connectors),
        "active_version": _version_summary(active_version),
        "created_at": operator.get("created_at"),
        "updated_at": operator.get("updated_at"),
    }


def _link_summary(link: dict) -> dict:
    return {
        "id": str(link["id"]),
        "from_operator_id": str(link["from_operator_id"]),
        "to_operator_id": str(link["to_operator_id"]),
        "environment": link.get("environment") or "",
        "link_type": link.get("link_type") or "",
        "task": link.get("task"),
        "notes": link.get("notes"),
        "created_by": link.get("created_by"),
        "created_at": link.get("created_at"),
    }


def _session_summary(session: dict) -> dict:
    return {
        "id": str(session["id"]),
        "operator_id": str(session["operator_id"]),
        "operator_version_id": str(session.get("operator_version_id"))
        if session.get("operator_version_id")
        else None,
        "title": session.get("title") or "",
        "status": session.get("status") or "planning",
        "environment": session.get("environment") or "",
        "current_task": session.get("current_task"),
        "context_entity_type": session.get("context_entity_type"),
        "context_entity_id": session.get("context_entity_id"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
    }


@router.get("", response_model=OperatorListResponse)
async def list_operators_route(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    include_inactive: bool = False,
) -> OperatorListResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operators = list_operators(client, org_id)
    operator_ids = [str(op["id"]) for op in operators]
    bindings = list_operator_bindings(client, org_id, operator_ids)
    connectors_by_operator: dict[str, list[str]] = {}
    connector_ids: list[str] = []
    for binding in bindings:
        op_id = str(binding.get("operator_id"))
        conn_id = binding.get("connector_id")
        if not op_id or not conn_id:
            continue
        connectors_by_operator.setdefault(op_id, []).append(str(conn_id))
        connector_ids.append(str(conn_id))
    connectors = list_connectors_by_ids(client, org_id, list(set(connector_ids)), environment)
    connector_map = {str(conn["id"]): conn for conn in connectors}
    workflow_counts: dict[str, int] = {}
    if operator_ids:
        nodes = (
            client.table("workflow_nodes")
            .select("operator_id, workflow_id")
            .eq("org_id", org_id)
            .eq("environment", environment)
            .in_("operator_id", operator_ids)
            .execute()
            .data
            or []
        )
        workflow_sets: dict[str, set[str]] = {}
        for node in nodes:
            op_id = node.get("operator_id")
            wf_id = node.get("workflow_id")
            if not op_id or not wf_id:
                continue
            workflow_sets.setdefault(str(op_id), set()).add(str(wf_id))
        workflow_counts = {op_id: len(wfs) for op_id, wfs in workflow_sets.items()}
    active_refs = list_active_versions(client, org_id, [str(op["id"]) for op in operators], environment)
    active_by_operator = {str(ref["operator_id"]): str(ref["active_version_id"]) for ref in active_refs}
    active_versions = list_operator_versions_by_ids(
        client, org_id, list(active_by_operator.values())
    )
    active_version_map = {str(v["id"]): v for v in active_versions}
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from exc
    if include_inactive and role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    filtered = []
    for op in operators:
        if not _env_allowed(op, environment):
            continue
        if not include_inactive and op.get("status") != "active":
            continue
        summary = _operator_summary(op)
        summary["environment"] = environment
        active_id = active_by_operator.get(str(op["id"]))
        summary["active_version"] = _version_summary(active_version_map.get(active_id))
        filtered.append(summary)
    return OperatorListResponse(operators=filtered)


@router.post("", response_model=OperatorDetail, status_code=status.HTTP_201_CREATED)
async def create_operator_route(
    body: OperatorCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorDetail:
    current_user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    allowed_envs = body.allowed_environments
    if allowed_envs is None:
        allowed_envs = [environment]
    allowed_envs = [env.strip() for env in allowed_envs if env and env.strip()]
    connectors = list_connectors_by_ids(client, org_id, body.connector_ids, environment)
    if body.connector_ids and len(connectors) != len(body.connector_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found in environment")
    operator = create_operator(
        client,
        org_id,
        {
            "name": body.name.strip(),
            "description": body.description,
            "status": body.status,
            "system_prompt": body.system_prompt,
            "role": body.role,
            "capabilities": body.capabilities,
            "config": body.config,
            "allowed_environments": allowed_envs,
            "requires_admin": body.requires_admin,
            "requires_approval": body.requires_approval,
            "approval_roles": body.approval_roles,
        },
        current_user.get("user_id"),
    )
    if body.connector_ids:
        set_operator_connectors(client, org_id, str(operator["id"]), body.connector_ids)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.created",
        resource_type="operator",
        resource_id=str(operator["id"]),
        metadata={"environment": environment},
    )
    return OperatorDetail(**_operator_detail(operator, connectors, None))


@router.get("/{operator_id}", response_model=OperatorDetail)
async def get_operator_route(
    operator_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorDetail:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if not _env_allowed(operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from exc
    if operator.get("status") != "active" and role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    bindings = list_operator_bindings(client, org_id, [str(operator_id)])
    connector_ids = [str(b["connector_id"]) for b in bindings if b.get("connector_id")]
    connectors = list_connectors_by_ids(client, org_id, connector_ids, environment)
    active_version = get_active_operator_version(client, org_id, str(operator_id), environment)
    return OperatorDetail(**_operator_detail(operator, connectors, active_version))


@router.patch("/{operator_id}", response_model=OperatorDetail)
async def update_operator_route(
    operator_id: UUID,
    body: OperatorUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorDetail:
    current_user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    allowed_envs = body.allowed_environments
    if allowed_envs is not None:
        allowed_envs = [env.strip() for env in allowed_envs if env and env.strip()]
    connectors = []
    if body.connector_ids is not None:
        connectors = list_connectors_by_ids(client, org_id, body.connector_ids, environment)
        if body.connector_ids and len(connectors) != len(body.connector_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found in environment")
        set_operator_connectors(client, org_id, str(operator_id), body.connector_ids)
    updated = update_operator(
        client,
        org_id,
        str(operator_id),
        {
            "name": body.name,
            "description": body.description,
            "status": body.status,
            "system_prompt": body.system_prompt,
            "role": body.role,
            "capabilities": body.capabilities,
            "config": body.config,
            "allowed_environments": allowed_envs,
            "requires_admin": body.requires_admin,
            "requires_approval": body.requires_approval,
            "approval_roles": body.approval_roles,
        },
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.updated",
        resource_type="operator",
        resource_id=str(operator_id),
        metadata={"environment": environment},
    )
    if not connectors:
        bindings = list_operator_bindings(client, org_id, [str(operator_id)])
        connector_ids = [str(b["connector_id"]) for b in bindings if b.get("connector_id")]
        connectors = list_connectors_by_ids(client, org_id, connector_ids, environment)
    active_version = get_active_operator_version(client, org_id, str(operator_id), environment)
    return OperatorDetail(**_operator_detail(updated, connectors, active_version))


@router.get("/{operator_id}/links", response_model=OperatorLinkListResponse)
async def list_operator_links_route(
    operator_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    direction: str | None = None,
) -> OperatorLinkListResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    direction_value = (direction or "outgoing").strip().lower()
    if direction_value not in {"outgoing", "incoming", "all"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid direction")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if not _env_allowed(operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    links = list_operator_links(client, org_id, str(operator_id), environment, direction_value)
    return OperatorLinkListResponse(links=[OperatorLinkSummary(**_link_summary(link)) for link in links])


@router.post("/{operator_id}/links", response_model=OperatorLinkSummary, status_code=status.HTTP_201_CREATED)
async def create_operator_link_route(
    operator_id: UUID,
    body: OperatorLinkCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorLinkSummary:
    current_user, org_id = _admin
    if str(operator_id) == body.to_operator_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Operator link must be to another operator")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    from_operator = get_operator(client, org_id, str(operator_id))
    if not from_operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if not _env_allowed(from_operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    to_operator = get_operator(client, org_id, body.to_operator_id)
    if not to_operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target operator not found")
    if not _env_allowed(to_operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Target operator not available in environment")
    link = create_operator_link(
        client,
        org_id=org_id,
        environment_name=environment,
        from_operator_id=str(operator_id),
        to_operator_id=body.to_operator_id,
        link_type=body.link_type,
        task=body.task,
        notes=body.notes,
        created_by=current_user.get("user_id"),
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.link.created",
        resource_type="operator_link",
        resource_id=str(link["id"]),
        metadata={
            "from_operator_id": str(operator_id),
            "to_operator_id": body.to_operator_id,
            "environment": environment,
        },
    )
    return OperatorLinkSummary(**_link_summary(link))


@router.delete("/{operator_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_operator_link_route(
    operator_id: UUID,
    link_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    current_user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    links = list_operator_links(client, org_id, str(operator_id), environment, "all")
    if not any(str(link.get("id")) == str(link_id) for link in links):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator link not found")
    removed = delete_operator_link(client, org_id, str(link_id))
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator link not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.link.deleted",
        resource_type="operator_link",
        resource_id=str(link_id),
        metadata={"operator_id": str(operator_id), "environment": environment},
    )
    return None


@router.get("/{operator_id}/versions", response_model=OperatorVersionListResponse)
async def list_operator_versions_route(
    operator_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorVersionListResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if not _env_allowed(operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from exc
    if operator.get("status") != "active" and role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    versions = list_operator_versions(client, org_id, str(operator_id), environment)
    return OperatorVersionListResponse(
        versions=[OperatorVersionSummary(**_version_summary(v)) for v in versions]
    )


@router.post("/{operator_id}/versions", response_model=OperatorVersionSummary, status_code=status.HTTP_201_CREATED)
async def create_operator_version_route(
    operator_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorVersionSummary:
    current_user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if not _env_allowed(operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    bindings = list_operator_bindings(client, org_id, [str(operator_id)])
    connector_ids = [str(b["connector_id"]) for b in bindings if b.get("connector_id")]
    connectors = list_connectors_by_ids(client, org_id, connector_ids, environment)
    if connector_ids and len(connectors) != len(connector_ids):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connector bindings missing in environment")
    version_number = get_next_operator_version_number(client, org_id, str(operator_id), environment)
    version = create_operator_version(
        client,
        org_id=org_id,
        operator_id=str(operator_id),
        environment_name=environment,
        payload={
            "version": version_number,
            "name": operator.get("name") or "",
            "description": operator.get("description"),
            "system_prompt": operator.get("system_prompt"),
            "role": operator.get("role"),
            "capabilities": operator.get("capabilities") or [],
            "config": operator.get("config") or {},
            "allowed_environments": operator.get("allowed_environments") or [],
            "requires_admin": operator.get("requires_admin") or False,
            "requires_approval": operator.get("requires_approval") or False,
            "approval_roles": operator.get("approval_roles") or [],
            "connector_ids": connector_ids,
        },
        created_by=current_user.get("user_id"),
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.version.created",
        resource_type="operator_version",
        resource_id=str(version["id"]),
        metadata={"operator_id": str(operator_id), "environment": environment, "version": version_number},
    )
    return OperatorVersionSummary(**_version_summary(version))


@router.post("/{operator_id}/versions/{version_id}/activate")
async def activate_operator_version_route(
    operator_id: UUID,
    version_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    current_user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if not _env_allowed(operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    version = get_operator_version(client, org_id, str(operator_id), environment, str(version_id))
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator version not found")
    set_active_operator_version(
        client,
        org_id=org_id,
        operator_id=str(operator_id),
        environment_name=environment,
        version_id=str(version_id),
        updated_by=current_user.get("user_id"),
    )
    client.table("operators").update(
        {"active_version_id": str(version_id)}
    ).eq("org_id", org_id).eq("id", str(operator_id)).execute()
    client.table("operator_versions").update(
        {"is_active": False}
    ).eq("org_id", org_id).eq("operator_id", str(operator_id)).eq("environment", environment).execute()
    client.table("operator_versions").update(
        {"is_active": True}
    ).eq("org_id", org_id).eq("id", str(version_id)).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.version.activated",
        resource_type="operator_version",
        resource_id=str(version_id),
        metadata={"operator_id": str(operator_id), "environment": environment},
    )
    return {"active_version_id": str(version_id), "version": int(version.get("version") or 0)}


@router.get("/{operator_id}/sessions", response_model=OperatorSessionListResponse)
async def list_operator_sessions_route(
    operator_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    scope: str | None = None,
) -> OperatorSessionListResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if not _env_allowed(operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from exc
    created_by = None
    if scope != "all" or role != "admin":
        created_by = current_user["user_id"]
    sessions = list_operator_sessions(client, org_id, str(operator_id), environment, created_by=created_by)
    return OperatorSessionListResponse(sessions=[_session_summary(s) for s in sessions])


@router.post("/{operator_id}/sessions", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_operator_session_route(
    operator_id: UUID,
    body: OperatorSessionCreateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if operator.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Operator is not active")
    if not _env_allowed(operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    active_version = get_active_operator_version(client, org_id, str(operator_id), environment)
    if not active_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active operator version for this environment",
        )
    session = create_operator_session(
        client,
        org_id,
        str(operator_id),
        environment,
        str(active_version["id"]),
        title=body.title.strip(),
        current_task=body.current_task,
        context_entity_type=None,
        context_entity_id=None,
        created_by=current_user.get("user_id"),
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.session.created",
        resource_type="operator_session",
        resource_id=str(session["id"]),
        metadata={"operator_id": str(operator_id), "environment": environment},
    )
    return _session_summary(session)


@router.get("/sessions/{session_id}", response_model=OperatorSessionDetail)
async def get_operator_session_route(
    session_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorSessionDetail:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    session = get_operator_session(client, org_id, str(session_id))
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.get("environment") != environment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from exc
    if role != "admin" and session.get("created_by") != current_user["user_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    operator = get_operator(client, org_id, str(session["operator_id"]))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    latest_plan = get_latest_action_plan(client, org_id, str(session_id))
    latest_plan_out = None
    if latest_plan:
        latest_plan_out = {
            "plan_id": str(latest_plan.get("id")),
            "title": latest_plan.get("title") or "",
            "summary": latest_plan.get("summary") or "",
            "steps": latest_plan.get("steps") or [],
            "guardrails": latest_plan.get("guardrails") or {},
            "status": latest_plan.get("status") or "draft",
            "operator_version_id": str(latest_plan.get("operator_version_id"))
            if latest_plan.get("operator_version_id")
            else None,
            "created_at": latest_plan.get("created_at"),
        }
    actions = [
        {
            "id": str(action.get("id")),
            "step_id": action.get("step_id") or "",
            "action_type": action.get("action_type") or "",
            "status": action.get("status") or "",
            "workflow_run_id": action.get("workflow_run_id"),
            "created_at": action.get("created_at"),
        }
        for action in list_operator_actions(client, org_id, str(session_id))
    ]
    return OperatorSessionDetail(
        session=_session_summary(session),
        operator=_operator_summary(operator),
        latest_plan=latest_plan_out,
        actions=actions,
    )


@router.post("/{operator_id}/action-plans", response_model=OperatorActionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_operator_action_plan_route(
    operator_id: UUID,
    body: OperatorActionPlanRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorActionPlanResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if operator.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Operator is not active")
    if not _env_allowed(operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    session = get_operator_session(client, org_id, body.session_id)
    if not session or str(session.get("operator_id")) != str(operator_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.get("environment") != environment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session environment mismatch")
    if not session.get("operator_version_id"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session missing operator version")
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from exc
    if role != "admin" and session.get("created_by") != current_user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted to update session")
    plan = build_operator_action_plan(
        client=client,
        settings=settings,
        operator=operator,
        org_id=org_id,
        environment=environment,
        primary_context=body.primary_context.model_dump(),
        related_contexts=[c.model_dump() for c in body.related_contexts],
        operator_goal=body.operator_goal,
    )
    stored = create_operator_action_plan(
        client,
        org_id=org_id,
        operator_id=str(operator_id),
        session_id=body.session_id,
        operator_version_id=str(session.get("operator_version_id")),
        environment_name=environment,
        title=plan.get("title") or "Action Plan",
        summary=plan.get("summary") or "",
        prompt=body.prompt,
        primary_context=body.primary_context.model_dump(),
        related_contexts=[c.model_dump() for c in body.related_contexts],
        steps=plan.get("steps") or [],
        guardrails=plan.get("guardrails") or {},
        created_by=current_user["user_id"],
    )
    update_operator_session_status(client, org_id, body.session_id, "review")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.plan.created",
        resource_type="operator_action_plan",
        resource_id=str(stored["id"]),
        metadata={"operator_id": str(operator_id), "environment": environment},
    )
    billing_plan = get_plan_for_org(client, org_id)
    period_start, period_end = get_current_period()
    ai_meta = build_ai_usage_metadata(
        input_texts=[body.operator_goal or "", body.prompt or ""],
        output_texts=[stored.get("summary") or ""],
        model_name=None,
        source="operator.action_plan",
        source_id=str(stored["id"]),
    )
    apply_usage_with_overage(
        client=client,
        org_id=org_id,
        environment=environment,
        metric_type="ai_credits",
        quantity=int(ai_meta["credits"]),
        plan=billing_plan,
        period_start=period_start,
        period_end=period_end,
        metadata=ai_meta,
    )
    return OperatorActionPlanResponse(
        plan_id=str(stored["id"]),
        title=stored.get("title") or "",
        summary=stored.get("summary") or "",
        steps=stored.get("steps") or [],
        guardrails=stored.get("guardrails") or {},
        status=stored.get("status") or "draft",
        operator_version_id=str(session.get("operator_version_id"))
        if session.get("operator_version_id")
        else None,
    )


@router.post("/{operator_id}/run", response_model=OperatorRunResponse)
async def run_operator_action_route(
    operator_id: UUID,
    body: OperatorRunRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperatorRunResponse:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(operator_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if operator.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Operator is not active")
    if not _env_allowed(operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator not available in environment")
    session = get_operator_session(client, org_id, body.session_id)
    if not session or str(session.get("operator_id")) != str(operator_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.get("environment") != environment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session environment mismatch")
    plan = get_latest_action_plan(client, org_id, body.session_id)
    if not plan or str(plan.get("id")) != body.plan_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")
    if not plan.get("operator_version_id"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Action plan missing operator version")
    if plan.get("operator_version_id") and session.get("operator_version_id"):
        if str(plan.get("operator_version_id")) != str(session.get("operator_version_id")):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Operator version mismatch")
    steps = list(plan.get("steps") or [])
    step = next((s for s in steps if s.get("id") == body.step_id), None)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    explanation = step.get("explanation") or {}
    if not explanation.get("executable"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Step is not executable")
    if not body.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmation required")
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from exc
    if operator.get("requires_admin") and role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

    workflow_id, parameters = resolve_execution_target(
        client,
        org_id,
        environment,
        plan.get("primary_context") or {},
        body.parameters,
    )
    result = await execute_operator_workflow(
        workflow_id=workflow_id,
        parameters=parameters,
        current_user=current_user,
        org_id=org_id,
        environment=environment,
        settings=settings,
    )
    action_status = "requested"
    approval_required = result.get("approval_required")
    approval_status = result.get("approval_status")
    workflow_status = result.get("status")
    if approval_required or approval_status == "pending_approval":
        action_status = "pending_approval"
        update_action_plan_status(client, org_id, body.plan_id, "pending_approval")
        update_operator_session_status(client, org_id, body.session_id, "awaiting_approval")
    elif workflow_status in {"running", "completed"}:
        action_status = "running" if workflow_status == "running" else "completed"
        update_action_plan_status(client, org_id, body.plan_id, "executing")
        update_operator_session_status(client, org_id, body.session_id, "executing")
    action = create_operator_action(
        client,
        org_id=org_id,
        operator_id=str(operator_id),
        session_id=body.session_id,
        plan_id=body.plan_id,
        operator_version_id=str(plan.get("operator_version_id")),
        step_id=body.step_id,
        action_type=step.get("step_type") or "execute_workflow",
        status=action_status,
        workflow_run_id=result.get("run_id"),
        created_by=current_user["user_id"],
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.action.requested",
        resource_type="operator_action",
        resource_id=str(action["id"]),
        metadata={
            "operator_id": str(operator_id),
            "plan_id": body.plan_id,
            "step_id": body.step_id,
            "workflow_run_id": result.get("run_id"),
            "environment": environment,
        },
    )
    return OperatorRunResponse(
        action_id=str(action["id"]),
        workflow_run_id=result.get("run_id"),
        status=action_status,
        approval_required=approval_required,
        approval_status=approval_status,
    )


@agents_router.get("")
async def list_agents_route(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    include_inactive: bool = False,
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operators = list_operators(client, org_id)
    active_refs = list_active_versions(client, org_id, [str(op["id"]) for op in operators], environment)
    active_by_operator = {str(ref["operator_id"]): str(ref["active_version_id"]) for ref in active_refs}
    active_versions = list_operator_versions_by_ids(
        client, org_id, list(active_by_operator.values())
    )
    active_version_map = {str(v["id"]): v for v in active_versions}
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from exc
    if include_inactive and role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    agents = []
    for op in operators:
        if not _env_allowed(op, environment):
            continue
        if not include_inactive and op.get("status") != "active":
            continue
        summary = _operator_summary(op)
        summary["environment"] = environment
        active_id = active_by_operator.get(str(op["id"]))
        summary["active_version"] = _version_summary(active_version_map.get(active_id))
        summary["active_version_id"] = active_id
        summary["version"] = (
            summary["active_version"].get("versionNumber") if summary.get("active_version") else None
        )
        op_id = str(op["id"])
        connected = [
            connector_map[cid]
            for cid in connectors_by_operator.get(op_id, [])
            if cid in connector_map
        ]
        summary["connectedSystems"] = _connected_systems(connected)
        summary["workflowCount"] = workflow_counts.get(op_id, 0)
        agents.append(summary)
    return {"agents": agents}


@agents_router.post("/suggest-icon")
async def suggest_agent_icon(
    body: AgentIconSuggestRequest,
    _user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    icon, confidence = _suggest_icon(body.name, body.purpose)
    color = _suggest_color(icon)
    return {
        "suggestedIcon": icon,
        "suggestedColor": color,
        "confidence": confidence,
    }


@agents_router.get("/{agent_id}")
async def get_agent_detail_route(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(agent_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if not _env_allowed(operator, environment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent not available in environment")
    try:
        role = get_user_role(client, org_id, current_user["user_id"])
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role validation failed") from exc
    if operator.get("status") != "active" and role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    bindings = list_operator_bindings(client, org_id, [str(agent_id)])
    connector_ids = [str(b["connector_id"]) for b in bindings if b.get("connector_id")]
    connectors = list_connectors_by_ids(client, org_id, connector_ids, environment)
    active_version = get_active_operator_version(client, org_id, str(agent_id), environment)
    versions = list_operator_versions(client, org_id, str(agent_id), environment)
    links = list_operator_links(client, org_id, str(agent_id), environment, "all")
    detail = _operator_detail(operator, connectors, active_version)
    detail["environment"] = environment
    nodes = (
        client.table("workflow_nodes")
        .select("workflow_id")
        .eq("org_id", org_id)
        .eq("environment", environment)
        .eq("operator_id", str(agent_id))
        .execute()
        .data
        or []
    )
    workflow_count = len({str(row["workflow_id"]) for row in nodes if row.get("workflow_id")})
    detail["workflowCount"] = workflow_count
    detail["connectedSystems"] = _connected_systems(connectors)
    detail["versions"] = [_version_summary(v) for v in versions]
    linked_agents = []
    for link in links:
        target_id = link.get("to_operator_id")
        if not target_id:
            continue
        target = get_operator(client, org_id, str(target_id))
        if target:
            summary = _operator_summary(target)
            summary["connectedSystems"] = []
            summary["workflowCount"] = 0
            linked_agents.append(summary)
    detail["linkedAgents"] = linked_agents
    return {"agent": detail, "versions": detail["versions"], "linkedAgents": detail["linkedAgents"]}


@agents_router.post("/{agent_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_agent_version_route(
    agent_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: AgentVersionCreateRequest | None = None,
) -> dict:
    if body is None:
        return await create_operator_version_route(agent_id, _admin, environment, settings)
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(agent_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    raw_version = body.version_number
    version_number = None
    if raw_version and str(raw_version).isdigit():
        version_number = int(raw_version)
    if version_number is None:
        version_number = get_next_operator_version_number(client, org_id, str(agent_id), environment)
    bindings = list_operator_bindings(client, org_id, [str(agent_id)])
    connector_ids = [str(b["connector_id"]) for b in bindings if b.get("connector_id")]
    version = create_operator_version(
        client,
        org_id=org_id,
        operator_id=str(agent_id),
        environment_name=environment,
        payload={
            "version": version_number,
            "name": body.name or operator.get("name") or "",
            "description": operator.get("description"),
            "system_prompt": operator.get("system_prompt"),
            "role": operator.get("role"),
            "capabilities": operator.get("capabilities") or [],
            "config": body.config or operator.get("config") or {},
            "allowed_environments": operator.get("allowed_environments") or [],
            "requires_admin": operator.get("requires_admin") or False,
            "requires_approval": operator.get("requires_approval") or False,
            "approval_roles": operator.get("approval_roles") or [],
            "connector_ids": connector_ids,
        },
        created_by=_user.get("user_id"),
    )
    return _version_summary(version)


@agents_router.patch("/{agent_id}/versions/{version_id}/activate")
async def activate_agent_version_route(
    agent_id: UUID,
    version_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return await activate_operator_version_route(agent_id, version_id, _admin, environment, settings)


@agents_router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent_route(
    body: AgentCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    current_user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    plan = get_plan_for_org(client, org_id)
    require_limit(len(list_operators(client, org_id)), plan.get("agents_limit"), "agents")
    _validate_icon(body.icon)
    _validate_avatar_color(body.avatar_color)
    avatar_color = body.avatar_color or _default_avatar_color(body.role, "active")
    operator = create_operator(
        client,
        org_id,
        {
            "name": body.name.strip(),
            "description": body.description,
            "status": "inactive",
            "role": body.role,
            "capabilities": body.capabilities or [],
            "config": body.config or {},
            "allowed_environments": [environment],
            "environment_id": body.environment_id,
            "icon": body.icon,
            "avatar_color": avatar_color,
        },
        current_user.get("user_id"),
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="agent.created",
        resource_type="agent",
        resource_id=str(operator["id"]),
        metadata={"environment": environment},
    )
    if body.icon is not None:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=current_user["user_id"],
            action="agent.icon.updated",
            resource_type="agent",
            resource_id=str(operator["id"]),
            metadata={"environment": environment, "icon": body.icon},
        )
    if body.avatar_color is not None:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=current_user["user_id"],
            action="agent.color.updated",
            resource_type="agent",
            resource_id=str(operator["id"]),
            metadata={"environment": environment, "avatarColor": avatar_color},
        )
    detail = _operator_detail(operator, [], None)
    detail["environment"] = environment
    detail["connectedSystems"] = []
    detail["workflowCount"] = 0
    return {"agent": detail}


@agents_router.patch("/{agent_id}")
async def update_agent_route(
    agent_id: UUID,
    body: AgentUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    current_user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    fields_set = getattr(body, "model_fields_set", getattr(body, "__fields_set__", set()))
    icon_field_set = "icon" in fields_set
    color_field_set = "avatar_color" in fields_set
    if icon_field_set:
        _validate_icon(body.icon)
    if color_field_set:
        _validate_avatar_color(body.avatar_color)
    existing = get_operator(client, org_id, str(agent_id))
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    payload = {
        "name": body.name,
        "description": body.description,
        "status": body.status,
        "role": body.role,
        "capabilities": body.capabilities,
        "config": body.config,
    }
    if icon_field_set:
        payload["icon"] = body.icon
    if color_field_set:
        payload["avatar_color"] = body.avatar_color
    updated = update_operator(
        client,
        org_id,
        str(agent_id),
        payload,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="agent.updated",
        resource_type="agent",
        resource_id=str(agent_id),
        metadata={"environment": environment},
    )
    if icon_field_set and body.icon != existing.get("icon"):
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=current_user["user_id"],
            action="agent.icon.updated",
            resource_type="agent",
            resource_id=str(agent_id),
            metadata={"environment": environment, "icon": body.icon},
        )
    if color_field_set and body.avatar_color != existing.get("avatar_color"):
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=current_user["user_id"],
            action="agent.color.updated",
            resource_type="agent",
            resource_id=str(agent_id),
            metadata={"environment": environment, "avatarColor": body.avatar_color},
        )
    bindings = list_operator_bindings(client, org_id, [str(agent_id)])
    connector_ids = [str(b["connector_id"]) for b in bindings if b.get("connector_id")]
    connectors = list_connectors_by_ids(client, org_id, connector_ids, environment)
    detail = _operator_detail(updated, connectors, get_active_operator_version(client, org_id, str(agent_id), environment))
    detail["environment"] = environment
    nodes = (
        client.table("workflow_nodes")
        .select("workflow_id")
        .eq("org_id", org_id)
        .eq("environment", environment)
        .eq("operator_id", str(agent_id))
        .execute()
        .data
        or []
    )
    detail["workflowCount"] = len({str(row["workflow_id"]) for row in nodes if row.get("workflow_id")})
    return {"agent": detail}


@agents_router.delete("/{agent_id}")
async def delete_agent_route(
    agent_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    operator = get_operator(client, org_id, str(agent_id))
    if not operator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    client.table("operators").update({"deleted_at": datetime.now(timezone.utc).isoformat(), "status": "inactive"}).eq(
        "id", str(agent_id)
    ).eq("org_id", org_id).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="agent.deleted",
        resource_type="agent",
        resource_id=str(agent_id),
        metadata={"environment": environment},
    )
    return {"success": True}


@sessions_router.get("")
async def list_sessions_route(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows = (
        client.table("sessions")
        .select("id, title, status, created_at, completed_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    activities = [
        {
            "id": str(row["id"]),
            "title": row.get("title") or "",
            "status": row.get("status") or "active",
            "createdAt": row.get("created_at"),
            "completedAt": row.get("completed_at"),
        }
        for row in rows
    ]
    return {"activities": activities, "sessions": activities}


@sessions_router.post("", status_code=status.HTTP_201_CREATED)
async def create_session_route(
    body: SessionCreateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = {
        "org_id": org_id,
        "user_id": current_user.get("user_id"),
        "title": body.title.strip(),
        "status": "active",
        "context_entity_type": body.context_entity_type,
        "context_entity_id": body.context_entity_id,
    }
    created = client.table("sessions").insert(row).execute()
    if not created.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Session create failed")
    session = created.data[0]
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.session.created",
        resource_type="session",
        resource_id=str(session["id"]),
        metadata={"environment": environment},
    )
    return {
        "session": {
            "id": str(session["id"]),
            "title": session.get("title") or "",
            "status": session.get("status") or "active",
            "contextEntityType": session.get("context_entity_type"),
            "contextEntityId": session.get("context_entity_id"),
            "createdAt": session.get("created_at"),
            "completedAt": session.get("completed_at"),
        }
    }


@sessions_router.post("/{session_id}/task", status_code=status.HTTP_201_CREATED)
async def submit_session_task(
    session_id: UUID,
    body: SessionTaskRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    session = (
        client.table("sessions")
        .select("id, title, status")
        .eq("org_id", org_id)
        .eq("id", str(session_id))
        .limit(1)
        .execute()
        .data
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    task_id = str(uuid.uuid4())
    summary = (body.task or "Automation task").strip()
    analysis = {
        "summary": f"Prepared an execution plan for: {summary}",
        "findings": [
            {
                "id": f"finding-{task_id[:8]}",
                "type": "insight",
                "icon": "sparkles",
                "title": "Automation ready",
                "description": "Key steps identified and ready for execution.",
            }
        ],
    }
    suggested_actions = [
        {
            "id": f"action-{task_id[:8]}-1",
            "title": "Run workflow",
            "description": "Execute the recommended workflow steps.",
            "type": "primary",
            "confidence": 86,
            "guardrailStatus": "passed",
            "requiresApproval": False,
            "estimatedDuration": "2m",
            "tokenCount": 420,
        }
    ]
    response = {
        "task": {
            "id": task_id,
            "description": summary,
            "status": "planning",
        },
        "analysis": analysis,
        "suggestedActions": suggested_actions,
        "nextSteps": {
            "canExecute": True,
            "requiresApproval": False,
            "approvalReason": None,
            "executeLabel": "Execute now",
        },
        "context": {
            "execution": {"label": "Execution", "description": "How the automation will run", "items": []},
            "automation": {"label": "Automation", "description": "What this automation does", "items": []},
            "connectedSystems": {
                "label": "Connected Systems",
                "description": "Data sources being used",
                "items": [],
            },
            "guardrails": {"label": "Guardrails", "description": "Safety checks in place", "items": []},
        },
    }
    client.table("session_messages").insert(
        {
            "session_id": str(session_id),
            "type": "action_plan",
            "content": response,
        }
    ).execute()
    plan = get_plan_for_org(client, org_id)
    period_start, period_end = get_current_period()
    output_texts = [analysis.get("summary") or ""]
    output_texts.extend([a.get("title") or "" for a in suggested_actions])
    ai_meta = build_ai_usage_metadata(
        input_texts=[body.task or summary],
        output_texts=output_texts,
        model_name=None,
        source="operator.task",
        source_id=str(session_id),
    )
    apply_usage_with_overage(
        client=client,
        org_id=org_id,
        environment=environment,
        metric_type="ai_credits",
        quantity=int(ai_meta["credits"]),
        plan=plan,
        period_start=period_start,
        period_end=period_end,
        metadata=ai_meta,
    )
    record_usage(
        client=client,
        org_id=org_id,
        environment=environment,
        metric_type="operator_usage",
        quantity=get_default_usage_quantity("operator_usage"),
        period_start=period_start,
        period_end=period_end,
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.task.submitted",
        resource_type="session",
        resource_id=str(session_id),
        metadata={"environment": environment},
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.task.analyzed",
        resource_type="session",
        resource_id=str(session_id),
        metadata={"environment": environment, "task_id": task_id},
    )
    return response


@sessions_router.get("/{session_id}/context")
async def get_session_context(
    session_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return {"sessionId": str(session_id), "packs": []}


@sessions_router.get("/{session_id}")
async def get_session_detail(
    session_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    session = (
        client.table("sessions")
        .select(
            "id, title, status, context_entity_type, context_entity_id, created_at, completed_at"
        )
        .eq("org_id", org_id)
        .eq("id", str(session_id))
        .limit(1)
        .execute()
        .data
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session_row = session[0]
    messages = (
        client.table("session_messages")
        .select("id, type, content, timestamp")
        .eq("session_id", str(session_id))
        .order("timestamp", desc=False)
        .execute()
        .data
        or []
    )
    return {
        "session": {
            "id": str(session_row["id"]),
            "title": session_row.get("title") or "",
            "status": session_row.get("status") or "active",
            "contextEntityType": session_row.get("context_entity_type"),
            "contextEntityId": session_row.get("context_entity_id"),
            "createdAt": session_row.get("created_at"),
            "completedAt": session_row.get("completed_at"),
        },
        "messages": [
            {
                "id": str(msg["id"]),
                "type": msg.get("type"),
                "content": msg.get("content") or {},
                "timestamp": msg.get("timestamp"),
            }
            for msg in messages
        ],
    }


@sessions_router.post("/{session_id}/execute")
async def execute_session_actions(
    session_id: UUID,
    body: SessionExecuteRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    session = (
        client.table("sessions")
        .select("id")
        .eq("org_id", org_id)
        .eq("id", str(session_id))
        .limit(1)
        .execute()
        .data
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    execution = client.table("task_executions").insert(
        {
            "session_id": str(session_id),
            "status": "running",
            "progress": 0,
            "current_step": body.action_ids[0] if body.action_ids else None,
            "results": [],
        }
    ).execute()
    if not execution.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Execution create failed")
    execution_id = str(execution.data[0]["id"])
    plan = get_plan_for_org(client, org_id)
    period_start, period_end = get_current_period()
    record_usage(
        client=client,
        org_id=org_id,
        environment=environment,
        metric_type="operator_usage",
        quantity=get_default_usage_quantity("operator_usage"),
        period_start=period_start,
        period_end=period_end,
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="operator.task.executed",
        resource_type="session",
        resource_id=str(session_id),
        metadata={"environment": environment, "execution_id": execution_id},
    )
    return {"executionId": execution_id, "status": "started", "message": "Execution started"}


@sessions_router.get("/{session_id}/execution/{execution_id}")
async def get_session_execution(
    session_id: UUID,
    execution_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    execution = (
        client.table("task_executions")
        .select("id, status, progress, current_step, results")
        .eq("id", str(execution_id))
        .eq("session_id", str(session_id))
        .limit(1)
        .execute()
        .data
    )
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    row = execution[0]
    return {
        "status": row.get("status") or "running",
        "progress": row.get("progress") or 0,
        "currentStep": row.get("current_step"),
        "results": row.get("results") or [],
    }
