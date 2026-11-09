from __future__ import annotations

import uuid
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.logging import get_logger
from app.services.model_router import ModelRouter, TaskType, get_model_router

logger = get_logger(__name__)

def _connector_actions() -> dict[str, list[str]]:
    from app.connectors.action_catalog import connector_actions_for_goal_service

    return connector_actions_for_goal_service()


CONNECTOR_ACTIONS = _connector_actions()


class GoalAnalysis(BaseModel):
    intent: str
    department: str
    objective_family: str | None = None
    connected_systems: list[str] = Field(default_factory=list)
    missing_systems: list[str] = Field(default_factory=list)
    understanding_status: str = "ANALYZED_UNVERIFIED"
    execution_status: str = "NOT_RUN"
    key_entities: list[str]
    required_systems: list[str]
    complexity: str
    risk_factors: list[str]
    success_metrics: list[str]



class BusinessMetricEvidence(BaseModel):
    """Read-only metric observation from a tenant-authorized source of record.

    A connection's existence or an LLM's claim is NOT evidence. Callers must
    supply an independently observed source record and a concrete metric unit.
    """
    org_id: str
    system: str
    source_record_id: str
    metric_key: str
    unit: str
    value: float
    observed_at: datetime

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("metric_value_must_be_finite")
        return value


class GoalEvidenceAssessment(BaseModel):
    status: str
    usable: list[BusinessMetricEvidence] = Field(default_factory=list)
    excluded: list[dict[str, str]] = Field(default_factory=list)
    missing_systems: list[str] = Field(default_factory=list)
    business_outcome: str = "NOT_MEASURED"



class ObservedMetricChange(BaseModel):
    """A bounded arithmetic observation, never a causal lift or forecast."""
    status: str
    metric_key: str | None = None
    system: str | None = None
    source_record_id: str | None = None
    unit: str | None = None
    before: float | None = None
    after: float | None = None
    absolute_change: float | None = None
    percentage_change: float | None = None
    interpretation: str = "OBSERVATION_ONLY_NOT_CAUSAL"
    business_outcome: str = "NOT_MEASURED"



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
        analysis: GoalAnalysis | None = None,
    ) -> WorkflowDefinition:
        analysis = analysis or await self._analyze_goal(goal, department, connectors, success_metric, org_context, org_id)
        definition = self._build_definition(goal, analysis, approval_required)
        self._validate_definition(definition)
        return definition

    async def analyze_for_org(
        self, *,
        goal: str,
        org_id: str,
        settings: Any,
        department_hint: str | None = None,
        success_metric: str | None = None,
        org_context: str | None = None,
    ) -> GoalAnalysis:
        """Canonical semantic intake; obtain connectors from the tenant, never prompt.

        Authorization to org_id is verified by the calling router. No execution
        is initiated here. Inferred required systems are diagnostic requirements,
        not proof of connection or action permission.
        """
        if not org_id or not org_id.strip():
            raise ValueError("authenticated_org_required")
        if not goal or not goal.strip():
            raise ValueError("business_goal_required")
        from app.services.agent_selector import AgentSelector

        connected = await AgentSelector(settings=settings)._get_connected(org_id)
        analysis = await self._analyze_goal(
            goal, department_hint, sorted(connected),
            success_metric, org_context, org_id,
        )
        return self.normalize_analysis(analysis, connected)

    @staticmethod
    def normalize_analysis(analysis: GoalAnalysis, connected: set[str]) -> GoalAnalysis:
        """Annotate semantics with actual tenant connection availability.

        Keep all model-inferred missing systems visible without trusting them
        as connection or permission grants.
        """
        required = list(dict.fromkeys(
            str(item).strip().lower()
            for item in analysis.required_systems
            if str(item).strip()
        ))
        return analysis.model_copy(update={
            "department": (analysis.department or "cross_functional").strip().lower(),
            "required_systems": required,
            "connected_systems": [item for item in required if item in connected],
            "missing_systems": [item for item in required if item not in connected],
            "understanding_status": (
                "FALLBACK_UNVERIFIED"
                if analysis.understanding_status == "FALLBACK_UNVERIFIED"
                else "ANALYZED_UNVERIFIED"
            ),
            "execution_status": "NOT_RUN",
        })

    @staticmethod
    def assess_evidence_for_org(
        *,
        org_id: str,
        analysis: GoalAnalysis,
        connected_systems: set[str],
        observations: list[BusinessMetricEvidence],
        as_of: datetime,
        max_age: timedelta = timedelta(days=7),
    ) -> GoalEvidenceAssessment:
        """Classify supplied metric records; never fetch, authorize or execute.

        The caller must already have authenticated the tenant and retrieved
        observations through governed connectors. Missing/stale evidence stays
        visible and cannot be converted into an asserted business outcome.
        """
        if not org_id or not org_id.strip():
            raise ValueError("authenticated_org_required")
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("timezone_aware_as_of_required")
        if max_age <= timedelta(0):
            raise ValueError("positive_evidence_freshness_required")
        now = as_of.astimezone(timezone.utc)
        connected = {system.strip().lower() for system in connected_systems}
        required = {system.strip().lower() for system in analysis.required_systems}
        usable: list[BusinessMetricEvidence] = []
        excluded: list[dict[str, str]] = []
        for record in observations:
            # A cross-tenant record is a security violation, not merely a
            # missing-data warning; never expose even its source identifier.
            if record.org_id != org_id:
                raise ValueError("cross_tenant_metric_evidence")
            system = record.system.strip().lower()
            reason = None
            if system not in connected or system not in required:
                reason = "unverified_or_unrequired_source"
            elif not (record.source_record_id.strip() and record.metric_key.strip() and record.unit.strip()):
                reason = "missing_metric_provenance"
            elif record.observed_at.tzinfo is None or record.observed_at.utcoffset() is None:
                reason = "missing_observation_timezone"
            else:
                observed = record.observed_at.astimezone(timezone.utc)
                if observed > now:
                    reason = "future_observation"
                elif now - observed > max_age:
                    reason = "stale_observation"
            if reason:
                excluded.append({"system": system, "metric_key": record.metric_key, "reason": reason})
            else:
                usable.append(record)
        return GoalEvidenceAssessment(
            status="EVIDENCE_AVAILABLE_UNINTERPRETED" if usable else "INSUFFICIENT_EVIDENCE",
            usable=usable,
            excluded=excluded,
            missing_systems=sorted(required - connected),
        )

    @staticmethod
    def evidence_from_verified_step(
        *,
        org_id: str,
        step: dict[str, Any],
    ) -> BusinessMetricEvidence:
        """Normalize a single independently verified, persisted read snapshot.

        This adapter cannot authorize a provider read. The existing workflow
        runtime must already have executed and persisted the result. Never
        interpret arbitrary free-form model output as verified business data.
        """
        if not org_id or not org_id.strip():
            raise ValueError("authenticated_org_required")
        if step.get("org_id") != org_id:
            raise ValueError("cross_tenant_metric_evidence")
        if step.get("status") != "completed" or step.get("kind") != "read":
            raise ValueError("verified_completed_read_required")
        if step.get("provider_readback_verified") is not True:
            raise ValueError("independent_provider_readback_required")
        snapshot = step.get("output_snapshot")
        if not isinstance(snapshot, dict):
            raise ValueError("structured_metric_snapshot_required")
        # Only the typed observation envelope is accepted. Generic connector
        # results need explicit, separately reviewed provider adapters.
        metric = snapshot.get("verified_metric")
        if not isinstance(metric, dict):
            raise ValueError("verified_metric_envelope_required")
        if not all(key in metric for key in (
            "system", "source_record_id", "metric_key",
            "unit", "value", "observed_at",
        )):
            raise ValueError("incomplete_verified_metric")
        if not step.get("source_record_id") or (
            str(step["source_record_id"]) != str(metric["source_record_id"])
        ):
            raise ValueError("metric_source_mismatch")
        if str(step.get("provider") or "").strip().lower() != str(metric["system"]).strip().lower():
            raise ValueError("metric_provider_mismatch")
        return BusinessMetricEvidence.model_validate({
            "org_id": org_id,
            **{key: metric[key] for key in (
                "system", "source_record_id", "metric_key",
                "unit", "value", "observed_at",
            )},
        })

    @staticmethod
    def compare_metric_observations(
        *, assessment: GoalEvidenceAssessment,
        metric_key: str,
    ) -> ObservedMetricChange:
        """Compare exactly two same-record snapshots without inventing impact.

        Data must first pass assess_evidence_for_org. Ambiguous source, record,
        unit, repeated timestamps or incomplete histories are not comparable.
        Only arithmetic differences are returned; no forecasts or action claims.
        """
        records = [item for item in assessment.usable if item.metric_key == metric_key]
        if assessment.status != "EVIDENCE_AVAILABLE_UNINTERPRETED" or len(records) != 2:
            return ObservedMetricChange(status="INSUFFICIENT_COMPARABLE_HISTORY")
        before, after = sorted(records, key=lambda item: item.observed_at)
        same_series = (
            before.org_id == after.org_id
            and before.system.strip().lower() == after.system.strip().lower()
            and before.source_record_id == after.source_record_id
            and before.unit == after.unit
            and before.observed_at < after.observed_at
        )
        if not same_series:
            return ObservedMetricChange(status="INCOMPATIBLE_METRIC_HISTORY")
        delta = after.value - before.value
        if not math.isfinite(delta):
            return ObservedMetricChange(status="INCOMPATIBLE_METRIC_HISTORY")
        ratio = (delta / abs(before.value)) * 100 if before.value else None
        if ratio is not None and not math.isfinite(ratio):
            ratio = None
        return ObservedMetricChange(
            status="OBSERVED_CHANGE_NOT_CAUSAL",
            metric_key=metric_key, system=before.system,
            source_record_id=before.source_record_id,
            unit=before.unit,
            before=before.value, after=after.value,
            absolute_change=delta,
            percentage_change=ratio,
        )

    async def _analyze_goal(
        self,
        goal: str,
        department: str | None,
        connectors: list[str] | None,
        success_metric: str | None,
        org_context: str | None,
        org_id: str | None,
    ) -> GoalAnalysis:
        from app.capability_ontology.meson_recipe_hints import format_recipe_prompt_section

        recipe_section = format_recipe_prompt_section(
            department=department,
            connected_integrations=connectors,
            query=goal,
        )
        prompt = (
            "Analyze this business goal for workflow generation.\n"
            f"Goal: {goal}\n"
            f"Department hint: {department or 'none'}\n"
            f"Verified tenant-connected providers (availability only): {connectors or []}\n"
            f"User-suggested success metric (unverified): {success_metric or 'none'}\n"
            f"User-supplied contextual notes (unverified): {org_context or 'none'}\n"
            "Identify business systems required for diagnosis even when disconnected; "
            "never assert the model can access them. Connector connections, scopes "
            "and external write approvals are checked by runtime policy, not this analysis.\n"
        )
        if recipe_section:
            prompt += f"\n{recipe_section}\n"
        prompt += (
            "Return ONLY strict JSON matching this schema (no markdown, no prose):\n"
            '{"intent": "<concise restatement of the goal>", '
            '"department": "<owning department, e.g. sales, marketing, operations, finance, support>", '
            '"objective_family": "<semantic goal category e.g. grow_revenue, reduce_cost, reduce_churn, improve_support, improve_operations, improve_security, or other>", '
            '"key_entities": ["..."], '
            '"required_systems": ["<systems needed for diagnosis, even if not connected>"], '
            '"complexity": "<one of: simple, moderate, complex>", '
            '"risk_factors": ["..."], '
            '"success_metrics": ["..."]}'
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

        # A failed model does NOT justify inventing "operations" ownership,
        # a business KPI target or an execution-ready plan.
        selected_dept = (department or "cross_functional").lower()
        selected_connectors = [c for c in (connectors or []) if c in CONNECTOR_ACTIONS]
        return GoalAnalysis(
            intent=goal,
            department=selected_dept,
            key_entities=["records", "stakeholders"],
            required_systems=selected_connectors,
            complexity="moderate",
            risk_factors=["insufficient_verified_context"],
            success_metrics=[success_metric] if success_metric else [],
            objective_family=None,
            understanding_status="FALLBACK_UNVERIFIED",
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
        """Fail closed on malformed planning graphs before handing them to the builder.

        This is a structural draft check, NOT proof that actions or connector
        scopes are executable. Runtime authorization remains authoritative.
        """
        node_ids = [node.id for node in workflow.nodes]
        if any(not node_id.strip() for node_id in node_ids) or len(set(node_ids)) != len(node_ids):
            raise ValueError("Workflow nodes require unique nonempty IDs")
        nodes = {node.id: node for node in workflow.nodes}
        if "start" not in nodes or "end" not in nodes:
            raise ValueError("Workflow must include start and end nodes")
        if nodes["start"].type != "trigger" or nodes["end"].type != "end":
            raise ValueError("Workflow start/end node types are invalid")
        edge_ids: set[str] = set()
        successors: dict[str, set[str]] = {node_id: set() for node_id in nodes}
        predecessors: dict[str, set[str]] = {node_id: set() for node_id in nodes}
        for edge in workflow.edges:
            if not edge.id.strip() or edge.id in edge_ids:
                raise ValueError("Workflow edges require unique nonempty IDs")
            edge_ids.add(edge.id)
            if edge.source not in nodes or edge.target not in nodes:
                raise ValueError("Workflow edge references unknown node")
            if edge.target == "start" or edge.source == "end":
                raise ValueError("Workflow start/end direction is invalid")
            if edge.target in successors[edge.source]:
                raise ValueError("Workflow contains duplicate connections")
            successors[edge.source].add(edge.target)
            predecessors[edge.target].add(edge.source)

        # Kahn's algorithm detects cycles even in an otherwise disconnected
        # component. A draft with unreachable or dead-end nodes is also unsafe.
        indegree = {node_id: len(parents) for node_id, parents in predecessors.items()}
        ready = [node_id for node_id, degree in indegree.items() if degree == 0]
        visited: set[str] = set()
        while ready:
            node_id = ready.pop()
            visited.add(node_id)
            for successor in successors[node_id]:
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    ready.append(successor)
        if len(visited) != len(nodes):
            raise ValueError("Workflow contains a cycle")

        def reachable(source: str, adjacency: dict[str, set[str]]) -> set[str]:
            found: set[str] = set()
            pending = [source]
            while pending:
                current = pending.pop()
                if current in found:
                    continue
                found.add(current)
                pending.extend(adjacency[current] - found)
            return found

        if reachable("start", successors) != set(nodes) or reachable("end", predecessors) != set(nodes):
            raise ValueError("Workflow contains disconnected or dead-end nodes")
        approvals = [node.id for node in workflow.nodes if node.type == "human_approval"]
        if workflow.requires_approval and not approvals:
            raise ValueError("Workflow requires an approval node")


_goal_service_singleton: GoalService | None = None


def get_goal_service() -> GoalService:
    global _goal_service_singleton
    if _goal_service_singleton is None:
        _goal_service_singleton = GoalService()
    return _goal_service_singleton
