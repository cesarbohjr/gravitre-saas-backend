from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.operator.schemas import ContextRef

OperatorStatus = Literal["draft", "active", "inactive"]
SessionStatus = Literal[
    "idle",
    "planning",
    "review",
    "awaiting_approval",
    "executing",
    "paused",
    "completed",
    "failed",
]
PlanStatus = Literal[
    "draft",
    "pending_approval",
    "approved",
    "executing",
    "completed",
    "failed",
    "cancelled",
]
ActionStatus = Literal[
    "requested",
    "pending_approval",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class OperatorConnector(BaseModel):
    id: str
    type: str
    status: str
    environment: str
    updated_at: str | None = None
    config: dict = Field(default_factory=dict)


class OperatorVersionSummary(BaseModel):
    id: str
    operator_id: str
    environment: str
    version: int
    name: str
    description: str | None = None
    role: str | None = None
    capabilities: list[str] = []
    config: dict = Field(default_factory=dict)
    created_at: str | None = None


class OperatorSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: OperatorStatus
    role: str | None = None
    capabilities: list[str] = []
    config: dict = Field(default_factory=dict)
    allowed_environments: list[str] = []
    requires_admin: bool
    requires_approval: bool
    approval_roles: list[str] = []
    active_version: OperatorVersionSummary | None = None


class OperatorDetail(OperatorSummary):
    system_prompt: str | None = None
    connectors: list[OperatorConnector] = []
    created_at: str | None = None
    updated_at: str | None = None


class OperatorLinkSummary(BaseModel):
    id: str
    from_operator_id: str
    to_operator_id: str
    environment: str
    link_type: str
    task: str | None = None
    notes: str | None = None
    created_by: str | None = None
    created_at: str | None = None


class OperatorLinkCreateRequest(BaseModel):
    to_operator_id: str = Field(..., min_length=1)
    link_type: str = Field(default="handoff", min_length=1)
    task: str | None = None
    notes: str | None = None


class OperatorLinkListResponse(BaseModel):
    links: list[OperatorLinkSummary]


class OperatorListResponse(BaseModel):
    operators: list[OperatorSummary]


class OperatorCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    status: OperatorStatus = "draft"
    system_prompt: str | None = None
    role: str | None = None
    capabilities: list[str] = []
    config: dict = Field(default_factory=dict)
    allowed_environments: list[str] | None = None
    requires_admin: bool = False
    requires_approval: bool = False
    approval_roles: list[str] = []
    connector_ids: list[str] = []


class OperatorUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: OperatorStatus | None = None
    system_prompt: str | None = None
    role: str | None = None
    capabilities: list[str] | None = None
    config: dict | None = None
    allowed_environments: list[str] | None = None
    requires_admin: bool | None = None
    requires_approval: bool | None = None
    approval_roles: list[str] | None = None
    connector_ids: list[str] | None = None


class OperatorSessionSummary(BaseModel):
    id: str
    operator_id: str
    operator_version_id: str | None = None
    title: str
    status: SessionStatus
    environment: str
    current_task: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class OperatorSessionDetail(BaseModel):
    session: OperatorSessionSummary
    operator: OperatorSummary
    latest_plan: dict | None = None
    actions: list[dict] = []


class OperatorSessionCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    current_task: str | None = None


class OperatorSessionListResponse(BaseModel):
    sessions: list[OperatorSessionSummary]


class OperatorActionPlanRequest(BaseModel):
    session_id: str
    primary_context: ContextRef
    related_contexts: list[ContextRef] = []
    operator_goal: str | None = None
    prompt: str | None = None


class OperatorActionPlanResponse(BaseModel):
    plan_id: str
    title: str
    summary: str
    steps: list[dict]
    guardrails: dict
    status: PlanStatus
    operator_version_id: str | None = None


class OperatorRunRequest(BaseModel):
    session_id: str
    plan_id: str
    step_id: str
    confirm: bool = False
    parameters: dict | None = None


class OperatorRunResponse(BaseModel):
    action_id: str
    workflow_run_id: str | None = None
    status: str
    approval_required: bool | None = None
    approval_status: str | None = None


class OperatorVersionListResponse(BaseModel):
    versions: list[OperatorVersionSummary]
