from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.model_router import ModelRouter, TaskType, get_model_router

logger = get_logger(__name__)

CONNECTOR_ACTIONS = {
    "hubspot": ["read_contacts", "update_contacts", "create_deals", "send_email", "read_lists"],
    "salesforce": ["read_leads", "update_leads", "create_opportunities", "read_accounts"],
    "slack": ["send_message", "create_channel", "read_messages"],
    "stripe": ["read_invoices", "read_subscriptions", "read_customers"],
    "gmail": ["send_email", "read_emails", "search_emails"],
    "zendesk": ["read_tickets", "create_tickets", "update_tickets"],
    "notion": ["read_pages", "create_pages", "update_pages"],
    "quickbooks": ["read_invoices", "create_invoices", "read_customers"],
}


class GoalAnalysis(BaseModel):
    intent: str
    department: str
    key_entities: list[str]
    required_systems: list[str]
    complexity: str
    risk_factors: list[str]
    success_metrics: list[str]


class WorkflowNode(BaseModel):
    id: str
    type: str
    name: str
    description: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str | None = None


class WorkflowDefinition(BaseModel):
    id: str
    name: str
    description: str
    goal: str
    department: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    required_connectors: list[str]
    estimated_duration_minutes: int
    risk_level: str
    requires_approval: bool
    success_criteria: list[str]


class GoalService:
    def __init__(self, model_router: ModelRouter | None = None):
        self.model_router = model_router or get_model_router()

    async def generate_workflow(
        self,
        goal: str,
        department: str | None = None,
        connectors: list[str] | None = None,
        success_metric: str | None = None,
        approval_required: bool = True,
        org_context: str | None = None,
        org_id: str | None = None,
    ) -> WorkflowDefinition:
        analysis = await self._analyze_goal(goal, department, connectors, success_metric, org_context, org_id)
        definition = self._build_definition(goal, analysis, approval_required)
        self._validate_definition(definition)
        return definition

    async def _analyze_goal(
        self,
        goal: str,
        department: str | None,
        connectors: list[str] | None,
        success_metric: str | None,
        org_context: str | None,
        org_id: str | None,
    ) -> GoalAnalysis:
        prompt = (
            "Analyze this business goal for workflow generation.\n"
            f"Goal: {goal}\n"
            f"Department hint: {department or 'none'}\n"
            f"Available connectors: {connectors or []}\n"
            f"Success metric: {success_metric or 'none'}\n"
            f"Context: {org_context or 'none'}\n"
            "Return strict JSON."
        )
        try:
            response = await self.model_router.complete(
                task_type=TaskType.WORKFLOW_PLANNING,
                prompt=prompt,
                response_format=GoalAnalysis,
                org_id=org_id,
            )
            if response.parsed:
                return GoalAnalysis.model_validate(response.parsed)
        except Exception as exc:  # noqa: BLE001
            logger.warning("goal analysis fallback used: %s", str(exc))

        selected_dept = (department or "operations").lower()
        selected_connectors = [c for c in (connectors or []) if c in CONNECTOR_ACTIONS]
        return GoalAnalysis(
            intent=goal,
            department=selected_dept,
            key_entities=["records", "stakeholders"],
            required_systems=selected_connectors,
            complexity="moderate",
            risk_factors=["data quality", "approval delays"],
            success_metrics=[success_metric or "completion_rate >= 90%"],
        )

    def _build_definition(self, goal: str, analysis: GoalAnalysis, approval_required: bool) -> WorkflowDefinition:
        workflow_id = str(uuid.uuid4())
        start_id = "start"
        process_id = "process"
        decision_id = "decision"
        approval_id = "approval"
        end_id = "end"

        nodes: list[WorkflowNode] = [
            WorkflowNode(
                id=start_id,
                type="trigger",
                name="Start",
                description="Workflow trigger",
                position={"x": 100.0, "y": 120.0},
            ),
            WorkflowNode(
                id=process_id,
                type="action",
                name="Process Inputs",
                description=f"Execute {analysis.intent}",
                config={"systems": analysis.required_systems},
                position={"x": 300.0, "y": 120.0},
            ),
            WorkflowNode(
                id=decision_id,
                type="decision",
                name="Evaluate Outcome",
                description="Assess success criteria and risk factors",
                config={"success_metrics": analysis.success_metrics, "risk_factors": analysis.risk_factors},
                position={"x": 520.0, "y": 120.0},
            ),
        ]
        edges: list[WorkflowEdge] = [
            WorkflowEdge(id="e1", source=start_id, target=process_id),
            WorkflowEdge(id="e2", source=process_id, target=decision_id),
        ]

        if approval_required:
            nodes.append(
                WorkflowNode(
                    id=approval_id,
                    type="human_approval",
                    name="Approval Gate",
                    description="Human review before finalizing",
                    position={"x": 740.0, "y": 120.0},
                )
            )
            edges.append(WorkflowEdge(id="e3", source=decision_id, target=approval_id))
            edges.append(WorkflowEdge(id="e4", source=approval_id, target=end_id))
        else:
            edges.append(WorkflowEdge(id="e3", source=decision_id, target=end_id))

        nodes.append(
            WorkflowNode(
                id=end_id,
                type="end",
                name="Complete",
                description="Workflow complete",
                position={"x": 960.0, "y": 120.0},
            )
        )
        return WorkflowDefinition(
            id=workflow_id,
            name=f"{analysis.department.title()} Automation",
            description=f"Auto-generated workflow for goal: {goal}",
            goal=goal,
            department=analysis.department,
            nodes=nodes,
            edges=edges,
            required_connectors=analysis.required_systems,
            estimated_duration_minutes=25 if analysis.complexity == "moderate" else 45,
            risk_level="medium" if analysis.risk_factors else "low",
            requires_approval=approval_required,
            success_criteria=analysis.success_metrics,
        )

    def _validate_definition(self, workflow: WorkflowDefinition) -> None:
        node_ids = {node.id for node in workflow.nodes}
        if "start" not in node_ids or "end" not in node_ids:
            raise ValueError("Workflow must include start and end nodes")
        for edge in workflow.edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                raise ValueError("Workflow edge references unknown node")


_goal_service_singleton: GoalService | None = None


def get_goal_service() -> GoalService:
    global _goal_service_singleton
    if _goal_service_singleton is None:
        _goal_service_singleton = GoalService()
    return _goal_service_singleton
