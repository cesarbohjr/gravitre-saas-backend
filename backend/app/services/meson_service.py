"""Meson build interpreter — turns wizard intent into agent + workflow plans (STA-161)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.operators.repository import create_operator
from app.services.goal_service import GoalService, get_goal_service
from app.services.model_router import ModelRouter, TaskType, get_model_router
from app.workflows.audit import write_audit_event
from app.workflows.constants import SCHEMA_VERSION

logger = get_logger(__name__)

DEPARTMENT_ROLE: dict[str, str] = {
    "marketing": "marketing",
    "sales": "sales",
    "operations": "default",
    "finance": "finance",
    "hr": "hr",
    "custom": "default",
}

DEPARTMENT_LABEL: dict[str, str] = {
    "marketing": "Marketing",
    "sales": "Sales",
    "operations": "Operations",
    "finance": "Finance",
    "hr": "HR",
    "custom": "Custom",
}

SYSTEM_CONNECTORS: dict[str, list[str]] = {
    "crm": ["hubspot", "salesforce"],
    "email": ["email"],
    "calendar": [],
    "data": ["webhook"],
    "messaging": ["slack"],
}


class MesonGeneratedConfig(BaseModel):
    agent: str
    agent_role: str | None = None
    agent_description: str | None = None
    training: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    sample_outputs: list[str] = Field(default_factory=list)


class MesonInterpretResult(BaseModel):
    intent: str
    department: str
    systems: list[str]
    output_types: list[str] = Field(default_factory=list, alias="outputTypes")
    generated_config: MesonGeneratedConfig = Field(alias="generatedConfig")
    confidence: float = 0.75
    explanation: str | None = None

    model_config = {"populate_by_name": True}


class MesonDeployResult(BaseModel):
    agent_id: str = Field(alias="agentId")
    workflow_id: str | None = Field(default=None, alias="workflowId")
    result: MesonInterpretResult

    model_config = {"populate_by_name": True}


class MesonInterpretPayload(BaseModel):
    """LLM structured output for interpret_build_request."""

    agent: str
    agent_role: str | None = None
    agent_description: str | None = None
    training: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    sample_outputs: list[str] = Field(default_factory=list)
    confidence: float = 0.75
    explanation: str | None = None


class MesonService:
    def __init__(
        self,
        model_router: ModelRouter | None = None,
        goal_service: GoalService | None = None,
    ) -> None:
        self.model_router = model_router or get_model_router()
        self.goal_service = goal_service or get_goal_service()

    async def interpret_build_request(
        self,
        *,
        intent: str,
        department: str,
        systems: list[str],
        output_types: list[str],
        org_id: str | None = None,
    ) -> MesonInterpretResult:
        cleaned_intent = intent.strip()
        dept = (department or "custom").lower()
        selected_systems = [s for s in systems if s]
        selected_outputs = [o for o in output_types if o]

        prompt = (
            "You are Meson, Gravitre's system builder copilot.\n"
            "Turn the user's build request into a concrete agent + enablement plan.\n\n"
            f"Intent: {cleaned_intent}\n"
            f"Department: {dept}\n"
            f"Selected systems: {selected_systems}\n"
            f"Output types: {selected_outputs}\n\n"
            "Return ONLY strict JSON (no markdown) matching:\n"
            '{"agent": "<agent display name>", '
            '"agent_role": "<short role title>", '
            '"agent_description": "<1-2 sentence purpose>", '
            '"training": ["<knowledge sources to ingest>"], '
            '"workflows": ["<workflow names to automate>"], '
            '"sample_outputs": ["<example deliverables>"], '
            '"confidence": 0.0, '
            '"explanation": "<why this plan fits>"}'
        )

        parsed: MesonInterpretPayload | None = None
        try:
            response = await self.model_router.complete(
                task_type=TaskType.WORKFLOW_PLANNING,
                prompt=prompt,
                response_format=MesonInterpretPayload,
                org_id=org_id,
            )
            if response.parsed:
                parsed = MesonInterpretPayload.model_validate(response.parsed)
        except Exception as exc:  # noqa: BLE001
            logger.warning("meson interpret LLM fallback: %s", exc)

        if parsed is None:
            parsed = self._heuristic_plan(cleaned_intent, dept, selected_systems, selected_outputs)

        generated = MesonGeneratedConfig(
            agent=parsed.agent,
            agent_role=parsed.agent_role or DEPARTMENT_LABEL.get(dept, "Specialist"),
            agent_description=parsed.agent_description or cleaned_intent,
            training=parsed.training,
            workflows=parsed.workflows,
            sample_outputs=parsed.sample_outputs,
        )
        return MesonInterpretResult(
            intent=cleaned_intent,
            department=dept,
            systems=selected_systems,
            outputTypes=selected_outputs,
            generatedConfig=generated,
            confidence=parsed.confidence,
            explanation=parsed.explanation,
        )

    def _heuristic_plan(
        self,
        intent: str,
        department: str,
        systems: list[str],
        output_types: list[str],
    ) -> MesonInterpretPayload:
        label = DEPARTMENT_LABEL.get(department, "Custom")
        agent_name = f"{label} Agent"
        training = [
            "Brand voice and positioning guidelines",
            "ICP and persona documentation",
            "Historical performance benchmarks",
        ]
        if "crm" in systems:
            training.append("CRM field definitions and pipeline stages")
        if "email" in systems:
            training.append("Email templates and compliance rules")

        workflows: list[str] = []
        sample_outputs: list[str] = []
        if "workflows" in output_types:
            workflows = [
                "Intake and qualification workflow",
                "Approval routing workflow",
                "Delivery automation workflow",
            ]
        if "campaigns" in output_types:
            sample_outputs.append("Multi-step campaign sequence")
        if "reports" in output_types:
            sample_outputs.append("Weekly performance summary")
        if "sequences" in output_types:
            sample_outputs.append("Follow-up outreach sequence")
        if not sample_outputs:
            sample_outputs = [f"{label} execution brief", "Recommended next actions"]

        if not workflows and "workflows" in output_types:
            workflows = [f"{label} automation pipeline"]

        return MesonInterpretPayload(
            agent=agent_name,
            agent_role=f"{label} specialist",
            agent_description=intent[:500] or f"Automates {label.lower()} work for your team.",
            training=training,
            workflows=workflows or [f"{label} task runner"],
            sample_outputs=sample_outputs,
            confidence=0.55,
            explanation="Heuristic plan generated without LLM.",
        )

    async def deploy_build(
        self,
        *,
        client: Any,
        org_id: str,
        user_id: str,
        environment_name: str,
        plan: MesonInterpretResult,
        create_workflow: bool = True,
    ) -> MesonDeployResult:
        cfg = plan.generated_config
        persona_role = DEPARTMENT_ROLE.get(plan.department, "default")
        operator = create_operator(
            client,
            org_id,
            {
                "name": cfg.agent.strip(),
                "description": cfg.agent_description or plan.intent,
                "status": "inactive",
                "role": cfg.agent_role or persona_role,
                "capabilities": plan.output_types or ["tasks"],
                "config": {
                    "meson": True,
                    "department": plan.department,
                    "systems": plan.systems,
                    "trainingPlan": cfg.training,
                    "personaRole": persona_role,
                },
                "allowed_environments": [environment_name],
            },
            user_id,
        )
        agent_id = str(operator["id"])

        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user_id,
            action="meson.agent.created",
            resource_type="agent",
            resource_id=agent_id,
            metadata={"department": plan.department, "intent": plan.intent[:200]},
        )

        workflow_id: str | None = None
        wants_workflow = create_workflow and (
            "workflows" in plan.output_types or bool(cfg.workflows)
        )
        if wants_workflow:
            connectors = self._connectors_for_systems(plan.systems)
            generated = await self.goal_service.generate_workflow(
                goal=plan.intent,
                department=plan.department,
                connectors=connectors or None,
                approval_required=True,
                org_id=org_id,
            )
            definition = {
                "schema_version": SCHEMA_VERSION,
                "steps": [
                    {
                        "id": node.id,
                        "name": node.name,
                        "type": node.type,
                        "config": node.config,
                        "metadata": {
                            "description": node.description,
                            "position": node.position,
                        },
                    }
                    for node in generated.nodes
                ],
                "edges": [edge.model_dump() for edge in generated.edges],
            }
            row = {
                "org_id": org_id,
                "name": generated.name,
                "goal": generated.goal,
                "description": generated.description,
                "definition": definition,
                "schema_version": SCHEMA_VERSION,
                "status": "draft",
                "stage": "build",
                "version": "v1.0.0",
                "created_by": user_id,
            }
            created = client.table("workflow_defs").insert(row).execute()
            if created.data:
                workflow_id = str(created.data[0]["id"])
                write_audit_event(
                    client,
                    org_id=org_id,
                    actor_id=user_id,
                    action="meson.workflow.created",
                    resource_type="workflow",
                    resource_id=workflow_id,
                    metadata={"agentId": agent_id, "department": plan.department},
                )

        return MesonDeployResult(agentId=agent_id, workflowId=workflow_id, result=plan)

    @staticmethod
    def _connectors_for_systems(systems: list[str]) -> list[str]:
        connectors: list[str] = []
        for system in systems:
            for connector in SYSTEM_CONNECTORS.get(system, []):
                if connector not in connectors:
                    connectors.append(connector)
        return connectors


_meson_service: MesonService | None = None


def get_meson_service() -> MesonService:
    global _meson_service
    if _meson_service is None:
        _meson_service = MesonService()
    return _meson_service
