"""Meson build interpreter — turns wizard intent into agent + workflow plans (STA-161/142)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings
from app.connectors.connection_health import resolve_connector_auth_status
from app.connectors.repository import list_connectors
from app.core.logging import get_logger
from app.operators.repository import create_operator
from app.services.goal_service import GoalService, get_goal_service
from app.services.model_router import ModelRouter, TaskType, get_model_router
from app.services.workflow_failure_prediction_service import list_failure_alerts
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


class MesonSuggestion(BaseModel):
    id: str
    node_type: str = Field(alias="nodeType")
    label: str
    reason: str | None = None
    confidence: float = 0.7

    model_config = {"populate_by_name": True}


class MesonSuggestionsResponse(BaseModel):
    suggestions: list[MesonSuggestion] = Field(default_factory=list)


class MesonAlert(BaseModel):
    id: str
    severity: str = "info"
    title: str
    message: str
    auto_fixable: bool = Field(default=False, alias="autoFixable")

    model_config = {"populate_by_name": True}


class MesonAlertsResponse(BaseModel):
    alerts: list[MesonAlert] = Field(default_factory=list)


class MesonInsight(BaseModel):
    id: str
    title: str
    summary: str
    category: str | None = None


class MesonInsightsResponse(BaseModel):
    insights: list[MesonInsight] = Field(default_factory=list)


class MesonFeedbackResult(BaseModel):
    ok: bool = True


class MesonSuggestionFeedbackStat(BaseModel):
    suggestion_id: str = Field(alias="suggestionId")
    accepted: int = 0
    dismissed: int = 0
    acceptance_rate: float | None = Field(default=None, alias="acceptanceRate")

    model_config = {"populate_by_name": True}


class MesonFeedbackMetricsResponse(BaseModel):
    accepted_count: int = Field(default=0, alias="acceptedCount")
    dismissed_count: int = Field(default=0, alias="dismissedCount")
    acceptance_rate: float | None = Field(default=None, alias="acceptanceRate")
    suggestions: list[MesonSuggestionFeedbackStat] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class MesonPreferencesResponse(BaseModel):
    department: str | None = None
    systems: list[str] = Field(default_factory=list)
    output_types: list[str] = Field(default_factory=list, alias="outputTypes")
    preferred_build_hours_utc: list[int] = Field(
        default_factory=list,
        alias="preferredBuildHoursUtc",
    )
    interpret_count: int = Field(default=0, alias="interpretCount")
    deploy_count: int = Field(default=0, alias="deployCount")

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
        user_id: str | None = None,
        client: Any | None = None,
    ) -> MesonInterpretResult:
        cleaned_intent = intent.strip()
        dept = (department or "custom").lower()
        selected_systems = [s for s in systems if s]
        selected_outputs = [o for o in output_types if o]

        preference_context = ""
        if client is not None and org_id and user_id:
            prefs = self.load_user_preferences(client, org_id, user_id)
            preference_context = self.format_preferences_for_prompt(prefs)

        prompt = (
            "You are Meson, Gravitre's system builder copilot.\n"
            "Turn the user's build request into a concrete agent + enablement plan.\n\n"
            f"Intent: {cleaned_intent}\n"
            f"Department: {dept}\n"
            f"Selected systems: {selected_systems}\n"
            f"Output types: {selected_outputs}\n"
        )
        if preference_context:
            prompt += f"\nUser build preferences (learned from prior Meson sessions):\n{preference_context}\n"
        prompt += (
            "\nReturn ONLY strict JSON (no markdown) matching:\n"
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
        result = MesonInterpretResult(
            intent=cleaned_intent,
            department=dept,
            systems=selected_systems,
            outputTypes=selected_outputs,
            generatedConfig=generated,
            confidence=parsed.confidence,
            explanation=parsed.explanation,
        )
        if client is not None and org_id and user_id:
            self.learn_user_preferences(
                client,
                org_id,
                user_id,
                department=dept,
                systems=selected_systems,
                output_types=selected_outputs,
                event="interpret",
            )
        return result

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

        self.learn_user_preferences(
            client,
            org_id,
            user_id,
            department=plan.department,
            systems=plan.systems,
            output_types=plan.output_types,
            event="deploy",
        )

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

    def get_workflow_suggestions(
        self,
        *,
        workflow_state: dict[str, Any] | None,
        last_added_node: dict[str, Any] | None,
        org_id: str,
        dismissed_ids: set[str] | None = None,
        feedback_summary: dict[str, Any] | None = None,
    ) -> MesonSuggestionsResponse:
        nodes = _parse_workflow_nodes(workflow_state)
        dismissed = set(dismissed_ids or set())
        if feedback_summary:
            dismissed.update(feedback_summary.get("dismissed_ids") or set())
        suggestions: list[MesonSuggestion] = []

        has_approval = any(str(n.get("type") or "") == "approval" for n in nodes)
        has_slack = any(str(n.get("vendor") or "").lower() == "slack" for n in nodes)
        has_validation = any(
            "valid" in str(n.get("name") or "").lower() or str(n.get("type") or "") == "agent"
            for n in nodes
        )
        has_decision = any(str(n.get("type") or "") == "decision" for n in nodes)
        has_data_processing = any(str(n.get("type") or "") in {"agent", "task"} for n in nodes)
        has_ingest = any(str(n.get("type") or "") in {"source", "connector"} for n in nodes)
        has_lead_scoring = any(
            token in str(n.get("name") or "").lower()
            for n in nodes
            for token in ("score", "lead", "enrich")
        )

        if not has_approval and len(nodes) >= 2:
            suggestions.append(
                MesonSuggestion(
                    id="add-approval",
                    nodeType="approval",
                    label="Quality Gate",
                    reason="Add approval step before production?",
                    confidence=0.82,
                )
            )

        if not has_slack and len(nodes) >= 3:
            suggestions.append(
                MesonSuggestion(
                    id="add-slack",
                    nodeType="connector",
                    label="Slack Notification",
                    reason="Add Slack notification step?",
                    confidence=0.74,
                )
            )

        if not has_validation and len(nodes) >= 1 and has_ingest:
            suggestions.append(
                MesonSuggestion(
                    id="add-validation",
                    nodeType="agent",
                    label="Data Validator",
                    reason="Add data validation step?",
                    confidence=0.78,
                )
            )

        if not has_decision and has_data_processing and len(nodes) >= 2:
            suggestions.append(
                MesonSuggestion(
                    id="add-decision",
                    nodeType="decision",
                    label="Route Decision",
                    reason="Add decision node for dynamic routing?",
                    confidence=0.76,
                )
            )

        if has_lead_scoring and not has_decision:
            suggestions.append(
                MesonSuggestion(
                    id="add-lead-routing",
                    nodeType="decision",
                    label="Evaluate Lead Quality",
                    reason="Add lead quality routing?",
                    confidence=0.8,
                )
            )

        last_type = str((last_added_node or {}).get("type") or "").lower()
        if last_type in {"hubspot_trigger", "source", "connector"} and not has_validation:
            suggestions.append(
                MesonSuggestion(
                    id="add-validation-after-ingest",
                    nodeType="agent",
                    label="Data Validator",
                    reason="Validate incoming data before downstream steps?",
                    confidence=0.85,
                )
            )

        filtered = [s for s in suggestions if s.id not in dismissed]
        ranked = _rank_suggestions_by_feedback(filtered, feedback_summary)
        return MesonSuggestionsResponse(suggestions=ranked[:5])

    def get_feedback_metrics(
        self,
        client: Any,
        org_id: str,
        *,
        workflow_id: str | None = None,
    ) -> MesonFeedbackMetricsResponse:
        summary = self.load_feedback_summary(client, org_id, workflow_id=workflow_id)
        return _feedback_summary_to_metrics(summary)

    def load_feedback_summary(
        self,
        client: Any,
        org_id: str,
        workflow_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            rows = (
                client.table("audit_events")
                .select("metadata")
                .eq("org_id", org_id)
                .eq("action", "meson.suggestion.feedback")
                .order("created_at", desc=True)
                .limit(500)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson feedback summary lookup failed: %s", exc)
            return _empty_feedback_summary()

        dismissed_ids: set[str] = set()
        by_suggestion: dict[str, dict[str, int]] = {}
        accepted_total = 0
        dismissed_total = 0

        for row in rows.data or []:
            meta = row.get("metadata") or {}
            if not isinstance(meta, dict):
                continue
            event_workflow_id = str(meta.get("workflowId") or "") or None
            if workflow_id and event_workflow_id and event_workflow_id != workflow_id:
                continue

            suggestion_id = str(meta.get("suggestionId") or "")
            if not suggestion_id:
                continue

            action = str(meta.get("action") or "").lower()
            stats = by_suggestion.setdefault(suggestion_id, {"accepted": 0, "dismissed": 0})
            if action == "dismissed":
                dismissed_ids.add(suggestion_id)
                stats["dismissed"] += 1
                dismissed_total += 1
            elif action == "accepted":
                stats["accepted"] += 1
                accepted_total += 1

        return {
            "dismissed_ids": dismissed_ids,
            "by_suggestion": by_suggestion,
            "accepted_count": accepted_total,
            "dismissed_count": dismissed_total,
        }

    def detect_anomalies(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
        settings: Settings,
    ) -> MesonAlertsResponse:
        alerts: list[MesonAlert] = []

        for row in list_failure_alerts(client, org_id, status="open", limit=20):
            alerts.append(
                MesonAlert(
                    id=str(row.get("id") or f"failure-{len(alerts)}"),
                    severity=str(row.get("severity") or "warning"),
                    title=str(row.get("title") or "Workflow risk detected"),
                    message=str(row.get("message") or "Review predicted failure before next run."),
                    autoFixable=False,
                )
            )

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            failed_runs = (
                client.table("workflow_runs")
                .select("id, workflow_id, error_message, created_at")
                .eq("org_id", org_id)
                .eq("environment", environment_name)
                .eq("status", "failed")
                .gte("created_at", cutoff)
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            )
            for run in failed_runs.data or []:
                run_id = str(run.get("id") or "")
                if any(a.id == f"run-failed-{run_id}" for a in alerts):
                    continue
                message = str(run.get("error_message") or "Workflow run failed recently.")
                alerts.append(
                    MesonAlert(
                        id=f"run-failed-{run_id}",
                        severity="critical",
                        title="Recent workflow failure",
                        message=message[:500],
                        autoFixable=False,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson alerts failed runs lookup: %s", exc)

        try:
            for connector in list_connectors(client, org_id, environment_name):
                vendor = str(connector.get("vendor") or connector.get("type") or "")
                connector_id = str(connector.get("id") or "")
                if not connector_id:
                    continue
                auth_status = resolve_connector_auth_status(
                    client,
                    org_id,
                    connector_id,
                    vendor,
                    settings,
                    environment_name=environment_name,
                )
                if auth_status in {"expired", "invalid", "revoked"}:
                    alerts.append(
                        MesonAlert(
                            id=f"connector-auth-{connector_id}",
                            severity="warning",
                            title=f"{vendor or 'Connector'} authentication issue",
                            message=f"Reconnect {vendor or 'connector'} to restore workflow reliability.",
                            autoFixable=True,
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson alerts connector lookup: %s", exc)

        return MesonAlertsResponse(alerts=alerts[:20])

    def get_proactive_insights(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
    ) -> MesonInsightsResponse:
        insights: list[MesonInsight] = []

        try:
            workflows = (
                client.table("workflow_defs")
                .select("id, status, stage")
                .eq("org_id", org_id)
                .limit(200)
                .execute()
            )
            rows = workflows.data or []
            draft_count = sum(1 for w in rows if str(w.get("status") or "") == "draft")
            if draft_count:
                insights.append(
                    MesonInsight(
                        id="draft-workflows",
                        title="Draft workflows ready to publish",
                        summary=f"{draft_count} workflow(s) are still in draft — publish when validation passes.",
                        category="workflow",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson insights workflow lookup: %s", exc)
            rows = []

        try:
            recent_runs = (
                client.table("workflow_runs")
                .select("status")
                .eq("org_id", org_id)
                .eq("environment", environment_name)
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            )
            statuses = [str(r.get("status") or "") for r in (recent_runs.data or [])]
            if statuses:
                success = sum(1 for s in statuses if s in {"completed", "success"})
                rate = round(success / len(statuses) * 100)
                if rate < 80:
                    insights.append(
                        MesonInsight(
                            id="run-success-rate",
                            title="Run success rate below target",
                            summary=f"Recent success rate is {rate}% — review failing steps and connector health.",
                            category="reliability",
                        )
                    )
                elif rate >= 95:
                    insights.append(
                        MesonInsight(
                            id="run-success-rate-good",
                            title="Strong workflow reliability",
                            summary=f"Recent success rate is {rate}% across the last {len(statuses)} runs.",
                            category="reliability",
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson insights run lookup: %s", exc)

        open_alerts = list_failure_alerts(client, org_id, status="open", limit=5)
        if open_alerts:
            insights.append(
                MesonInsight(
                    id="open-failure-alerts",
                    title="Predictive alerts need review",
                    summary=f"{len(open_alerts)} open failure prediction(s) — inspect before the next production run.",
                    category="risk",
                )
            )

        if not insights:
            insights.append(
                MesonInsight(
                    id="meson-ready",
                    title="Meson is monitoring your workspace",
                    summary="No urgent issues detected. Keep building — Meson will suggest next steps as you add nodes.",
                    category="general",
                )
            )

        return MesonInsightsResponse(insights=insights[:10])

    def record_feedback(
        self,
        client: Any,
        org_id: str,
        user_id: str,
        *,
        suggestion_id: str,
        action: str,
        reason: str | None = None,
        workflow_id: str | None = None,
    ) -> MesonFeedbackResult:
        normalized_action = action.strip().lower()
        if normalized_action not in {"accepted", "dismissed"}:
            raise ValueError("action must be accepted or dismissed")

        resource_id = workflow_id or suggestion_id
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user_id,
            action="meson.suggestion.feedback",
            resource_type="workflow" if workflow_id else "meson_suggestion",
            resource_id=resource_id,
            metadata={
                "suggestionId": suggestion_id,
                "action": normalized_action,
                "reason": (reason or "")[:500] or None,
                "workflowId": workflow_id,
            },
        )
        return MesonFeedbackResult(ok=True)

    def load_user_preferences(self, client: Any, org_id: str, user_id: str) -> dict[str, Any]:
        try:
            row = (
                client.table("meson_user_preferences")
                .select("preferences")
                .eq("org_id", org_id)
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson preferences load failed: %s", exc)
            return {}

        data = row.data if row else None
        if not isinstance(data, dict):
            return {}
        prefs = data.get("preferences")
        return dict(prefs) if isinstance(prefs, dict) else {}

    def learn_user_preferences(
        self,
        client: Any,
        org_id: str,
        user_id: str,
        *,
        department: str,
        systems: list[str],
        output_types: list[str],
        event: str,
    ) -> dict[str, Any]:
        current = self.load_user_preferences(client, org_id, user_id)
        updated = _merge_meson_preferences(
            current,
            department=department,
            systems=systems,
            output_types=output_types,
            event=event,
        )
        try:
            client.table("meson_user_preferences").upsert(
                {
                    "org_id": org_id,
                    "user_id": user_id,
                    "preferences": updated,
                },
                on_conflict="org_id,user_id",
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("meson preferences persist failed: %s", exc)
        return updated

    def get_user_preferences(
        self,
        client: Any,
        org_id: str,
        user_id: str,
    ) -> MesonPreferencesResponse:
        prefs = self.load_user_preferences(client, org_id, user_id)
        return _preferences_to_response(prefs)

    @staticmethod
    def format_preferences_for_prompt(prefs: dict[str, Any]) -> str:
        if not prefs:
            return ""

        lines: list[str] = []
        dept = _top_count_key(prefs.get("department_counts"))
        if dept:
            lines.append(f"- Preferred department: {dept}")

        systems = _top_count_keys(prefs.get("system_counts"), limit=4)
        if systems:
            lines.append(f"- Frequently selected systems: {', '.join(systems)}")

        outputs = _top_count_keys(prefs.get("output_type_counts"), limit=4)
        if outputs:
            lines.append(f"- Common output types: {', '.join(outputs)}")

        hours = _top_count_keys(prefs.get("build_hour_counts"), limit=3)
        if hours:
            lines.append(f"- Typical build hours (UTC): {', '.join(hours)}")

        interpret_count = int(prefs.get("interpret_count") or 0)
        deploy_count = int(prefs.get("deploy_count") or 0)
        if interpret_count or deploy_count:
            lines.append(f"- Prior Meson sessions: {interpret_count} plans, {deploy_count} deploys")

        return "\n".join(lines)

    def load_dismissed_suggestion_ids(
        self,
        client: Any,
        org_id: str,
        workflow_id: str | None,
    ) -> set[str]:
        summary = self.load_feedback_summary(client, org_id, workflow_id=workflow_id)
        return set(summary.get("dismissed_ids") or set())


def _empty_feedback_summary() -> dict[str, Any]:
    return {
        "dismissed_ids": set(),
        "by_suggestion": {},
        "accepted_count": 0,
        "dismissed_count": 0,
    }


def _feedback_summary_to_metrics(summary: dict[str, Any]) -> MesonFeedbackMetricsResponse:
    accepted = int(summary.get("accepted_count") or 0)
    dismissed = int(summary.get("dismissed_count") or 0)
    total = accepted + dismissed
    rate = round(accepted / total, 3) if total else None

    suggestion_stats: list[MesonSuggestionFeedbackStat] = []
    for suggestion_id, counts in (summary.get("by_suggestion") or {}).items():
        acc = int(counts.get("accepted") or 0)
        dis = int(counts.get("dismissed") or 0)
        subtotal = acc + dis
        suggestion_stats.append(
            MesonSuggestionFeedbackStat(
                suggestionId=str(suggestion_id),
                accepted=acc,
                dismissed=dis,
                acceptanceRate=round(acc / subtotal, 3) if subtotal else None,
            )
        )
    suggestion_stats.sort(key=lambda item: (-(item.accepted + item.dismissed), item.suggestion_id))

    return MesonFeedbackMetricsResponse(
        acceptedCount=accepted,
        dismissedCount=dismissed,
        acceptanceRate=rate,
        suggestions=suggestion_stats,
    )


def _rank_suggestions_by_feedback(
    suggestions: list[MesonSuggestion],
    feedback_summary: dict[str, Any] | None,
) -> list[MesonSuggestion]:
    if not suggestions:
        return []

    by_suggestion = (feedback_summary or {}).get("by_suggestion") or {}
    ranked: list[MesonSuggestion] = []

    for suggestion in suggestions:
        stats = by_suggestion.get(suggestion.id) or {}
        accepted = int(stats.get("accepted") or 0)
        dismissed = int(stats.get("dismissed") or 0)
        total = accepted + dismissed
        if total >= 2 and dismissed > accepted:
            continue

        confidence = suggestion.confidence
        if total:
            rate = accepted / total
            if rate >= 0.6:
                confidence = min(0.99, confidence + 0.05)
            elif rate <= 0.25 and dismissed >= 2:
                continue

        if confidence != suggestion.confidence:
            suggestion = suggestion.model_copy(update={"confidence": confidence})
        ranked.append(suggestion)

    ranked.sort(key=lambda item: item.confidence, reverse=True)
    return ranked


def _increment_count_map(counts: dict[str, Any] | None, key: str, amount: int = 1) -> dict[str, int]:
    merged: dict[str, int] = {}
    if isinstance(counts, dict):
        for raw_key, raw_value in counts.items():
            try:
                merged[str(raw_key)] = int(raw_value)
            except (TypeError, ValueError):
                continue
    merged[key] = merged.get(key, 0) + amount
    return merged


def _increment_count_maps(
    counts: dict[str, Any] | None,
    keys: list[str],
    amount: int = 1,
) -> dict[str, int]:
    merged: dict[str, int] = {}
    if isinstance(counts, dict):
        for raw_key, raw_value in counts.items():
            try:
                merged[str(raw_key)] = int(raw_value)
            except (TypeError, ValueError):
                continue
    for key in keys:
        if not key:
            continue
        merged[key] = merged.get(key, 0) + amount
    return merged


def _top_count_key(counts: dict[str, Any] | None) -> str | None:
    ranked = _top_count_keys(counts, limit=1)
    return ranked[0] if ranked else None


def _top_count_keys(counts: dict[str, Any] | None, *, limit: int) -> list[str]:
    if not isinstance(counts, dict) or not counts:
        return []
    scored: list[tuple[int, str]] = []
    for key, value in counts.items():
        try:
            scored.append((int(value), str(key)))
        except (TypeError, ValueError):
            continue
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [key for _, key in scored[:limit]]


def _merge_meson_preferences(
    current: dict[str, Any],
    *,
    department: str,
    systems: list[str],
    output_types: list[str],
    event: str,
) -> dict[str, Any]:
    prefs = dict(current or {})
    dept = (department or "custom").lower()
    prefs["department_counts"] = _increment_count_map(prefs.get("department_counts"), dept)
    prefs["system_counts"] = _increment_count_maps(prefs.get("system_counts"), systems)
    prefs["output_type_counts"] = _increment_count_maps(prefs.get("output_type_counts"), output_types)
    hour_key = str(datetime.now(timezone.utc).hour)
    prefs["build_hour_counts"] = _increment_count_map(prefs.get("build_hour_counts"), hour_key)
    prefs["last_department"] = dept
    prefs["last_systems"] = [s for s in systems if s]
    prefs["last_output_types"] = [o for o in output_types if o]
    if event == "deploy":
        prefs["deploy_count"] = int(prefs.get("deploy_count") or 0) + 1
    else:
        prefs["interpret_count"] = int(prefs.get("interpret_count") or 0) + 1
    return prefs


def _preferences_to_response(prefs: dict[str, Any]) -> MesonPreferencesResponse:
    hours = _top_count_keys(prefs.get("build_hour_counts"), limit=3)
    return MesonPreferencesResponse(
        department=_top_count_key(prefs.get("department_counts"))
        or (str(prefs.get("last_department")) if prefs.get("last_department") else None),
        systems=_top_count_keys(prefs.get("system_counts"), limit=5)
        or [str(x) for x in (prefs.get("last_systems") or []) if x],
        outputTypes=_top_count_keys(prefs.get("output_type_counts"), limit=5)
        or [str(x) for x in (prefs.get("last_output_types") or []) if x],
        preferredBuildHoursUtc=[int(h) for h in hours if str(h).isdigit()],
        interpretCount=int(prefs.get("interpret_count") or 0),
        deployCount=int(prefs.get("deploy_count") or 0),
    )


def _parse_workflow_nodes(workflow_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not workflow_state:
        return []
    nodes = workflow_state.get("nodes")
    if isinstance(nodes, list):
        return [node for node in nodes if isinstance(node, dict)]
    return []


_meson_service: MesonService | None = None


def get_meson_service() -> MesonService:
    global _meson_service
    if _meson_service is None:
        _meson_service = MesonService()
    return _meson_service
