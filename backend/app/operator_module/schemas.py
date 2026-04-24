from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ContextType = Literal["run", "workflow", "connector", "source"]


class ContextRef(BaseModel):
    type: ContextType
    id: str = Field(..., description="Entity UUID")


class ContextPackSummary(BaseModel):
    id: str
    type: ContextType
    title: str
    summary: str
    status: str
    environment: str
    href: str


class AuditEventSummary(BaseModel):
    action: str
    created_at: str


class AuditSummary(BaseModel):
    total_events: int
    recent_events: list[AuditEventSummary]


class RunStepSummary(BaseModel):
    step_index: int
    step_name: str
    step_type: str
    status: str
    error_code: str | None = None


class RunSummary(BaseModel):
    id: str
    workflow_id: str | None = None
    status: str
    approval_status: str | None = None
    approval_required: bool
    required_approvals: int
    approvals_received: int
    created_at: str | None = None
    environment: str


class RunReference(BaseModel):
    id: str
    status: str
    created_at: str | None = None
    workflow_id: str | None = None


class RunContextResponse(BaseModel):
    pack: ContextPackSummary
    run: RunSummary
    steps: list[RunStepSummary]
    recent_runs: list[RunReference]
    audit: AuditSummary
    environment: str


class WorkflowSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    schema_version: str | None = None
    updated_at: str | None = None


class WorkflowVersionSummary(BaseModel):
    id: str
    version: int
    created_at: str | None = None


class ConnectorReference(BaseModel):
    type: str
    step_types: list[str] = []


class WorkflowContextResponse(BaseModel):
    pack: ContextPackSummary
    workflow: WorkflowSummary
    active_version: WorkflowVersionSummary | None = None
    recent_versions: list[WorkflowVersionSummary]
    recent_runs: list[RunReference]
    linked_connectors: list[ConnectorReference]
    environment: str


class ConnectorSummary(BaseModel):
    id: str
    type: str
    status: str
    updated_at: str | None = None
    environment: str


class ConfigSummary(BaseModel):
    keys: list[str]
    field_count: int


class RelatedWorkflow(BaseModel):
    id: str
    name: str


class ConnectorContextResponse(BaseModel):
    pack: ContextPackSummary
    connector: ConnectorSummary
    config_summary: ConfigSummary
    related_workflows: list[RelatedWorkflow]
    environment: str


class SourceSummary(BaseModel):
    id: str
    title: str
    type: str
    updated_at: str | None = None
    environment: str


class DocumentSummary(BaseModel):
    id: str
    title: str | None = None
    updated_at: str | None = None
    external_id: str | None = None


class IngestJobSummary(BaseModel):
    id: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    error_code: str | None = None


class SourceContextResponse(BaseModel):
    pack: ContextPackSummary
    source: SourceSummary
    recent_documents: list[DocumentSummary]
    ingest_jobs: list[IngestJobSummary]
    environment: str


class ActionPlanRequest(BaseModel):
    primary_context: ContextRef
    related_contexts: list[ContextRef] = []
    operator_goal: str | None = None


class Explainability(BaseModel):
    data_used: list[str]
    environment: str
    permissions_required: list[str]
    approval_required: bool
    admin_required: bool
    executable: bool
    draft_only: bool
    confirmation_required: bool


class ActionPlanStep(BaseModel):
    id: str
    title: str
    description: str
    step_type: str
    linked_entity: ContextRef | None = None
    dependencies: list[str] = []
    explanation: Explainability


class GuardrailSummary(BaseModel):
    environment: str
    approval_requirements: list[str]
    admin_restrictions: list[str]
    execution_restrictions: list[str]


class ActionPlanResponse(BaseModel):
    plan_id: str
    title: str
    summary: str
    steps: list[ActionPlanStep]
    guardrails: GuardrailSummary
