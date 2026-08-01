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
from app.workflows.repository import list_org_workflow_schedules
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
    # Module C / STA-331: match MesonSuggestion — heuristic interpret scores are estimates.
    confidence_is_estimate: bool = Field(default=True, alias="confidenceIsEstimate")
    confidence_source: str = Field(default="heuristic", alias="confidenceSource")
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
    # Module C / STA-331: heuristic constants are estimates until feedback/outcomes compute them.
    confidence_is_estimate: bool = Field(default=True, alias="confidenceIsEstimate")
    confidence_source: str = Field(default="heuristic", alias="confidenceSource")

    model_config = {"populate_by_name": True}


class MesonSuggestionsResponse(BaseModel):
    suggestions: list[MesonSuggestion] = Field(default_factory=list)


class MesonAlert(BaseModel):
    id: str
    severity: str = "info"
    title: str
    message: str
    auto_fixable: bool = Field(default=False, alias="autoFixable")
    action_type: str | None = Field(default=None, alias="actionType")
    action_target: str | None = Field(default=None, alias="actionTarget")
    fix_label: str | None = Field(default=None, alias="fixLabel")

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


class MesonPageContextResponse(BaseModel):
    """Page-scoped Meson insights and suggestions for registry, agents, and AI chat."""

    insights: list[MesonInsight] = Field(default_factory=list)
    suggestions: list[MesonSuggestion] = Field(default_factory=list)
    source: str | None = None


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
    confidence_is_estimate: bool = Field(default=True, alias="confidenceIsEstimate")
    confidence_source: str = Field(default="heuristic", alias="confidenceSource")
    explanation: str | None = None

    model_config = {"populate_by_name": True}


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

        from app.services.gravitree_voice import apply_voice, confidence_register_hint

        # Same voice SoT as chat/ReAct (confidence register + humor budget included).
        # Meson→Module B planner unification is deferred.
        prompt = apply_voice(
            "ROLE: You are Meson, Gravitre's system builder copilot.\n"
            "Turn the user's build request into a concrete agent + enablement plan.\n"
            f"{confidence_register_hint('estimate')}\n"
            "Humor budget: off for this planning turn (governance-adjacent build advice).\n\n"
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
            confidenceIsEstimate=getattr(parsed, "confidence_is_estimate", True),
            confidenceSource=getattr(parsed, "confidence_source", "heuristic"),
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
        icon: str | None = None,
        avatar_color: str | None = None,
    ) -> MesonDeployResult:
        # Module 0 — same isolation guard as chat/ReAct/canvas write spine.
        from app.services.conversation_write_guard import assert_org_write_allowed

        assert_org_write_allowed(org_id, actor_id=user_id, resource="meson deploy")
        cfg = plan.generated_config
        persona_role = DEPARTMENT_ROLE.get(plan.department, "default")
        agent_name = cfg.agent.strip()
        valid_icons = {
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
        valid_colors = {
            "bg-emerald-500",
            "bg-blue-500",
            "bg-amber-500",
            "bg-purple-500",
            "bg-rose-500",
            "bg-cyan-500",
        }
        text = f"{agent_name} {plan.intent}".lower()
        if icon in valid_icons:
            resolved_icon = icon
        elif "marketing" in text:
            resolved_icon = "megaphone"
        elif "sales" in text:
            resolved_icon = "trending-up"
        elif "finance" in text or "report" in text:
            resolved_icon = "pie-chart"
        elif "support" in text or "customer" in text:
            resolved_icon = "headphones"
        elif "data" in text:
            resolved_icon = "database"
        else:
            resolved_icon = "bot"
        icon_color_map = {
            "megaphone": "bg-emerald-500",
            "trending-up": "bg-blue-500",
            "database": "bg-cyan-500",
            "pie-chart": "bg-purple-500",
            "headphones": "bg-amber-500",
            "bot": "bg-blue-500",
        }
        resolved_color = avatar_color if avatar_color in valid_colors else icon_color_map.get(resolved_icon, "bg-emerald-500")
        color_to_personality = {
            "bg-emerald-500": {"color": "emerald", "gradient": "from-emerald-500 to-teal-600", "glow": "shadow-emerald-500/30"},
            "bg-blue-500": {"color": "blue", "gradient": "from-blue-500 to-indigo-600", "glow": "shadow-blue-500/30"},
            "bg-amber-500": {"color": "amber", "gradient": "from-amber-500 to-orange-600", "glow": "shadow-amber-500/30"},
            "bg-purple-500": {"color": "purple", "gradient": "from-purple-500 to-violet-600", "glow": "shadow-purple-500/30"},
            "bg-rose-500": {"color": "rose", "gradient": "from-rose-500 to-pink-600", "glow": "shadow-rose-500/30"},
            "bg-cyan-500": {"color": "cyan", "gradient": "from-cyan-500 to-blue-600", "glow": "shadow-cyan-500/30"},
        }
        personality = color_to_personality.get(resolved_color, color_to_personality["bg-emerald-500"])
        operator = create_operator(
            client,
            org_id,
            {
                "name": agent_name,
                "description": cfg.agent_description or plan.intent,
                "status": "active",
                "role": cfg.agent_role or persona_role,
                "capabilities": plan.output_types or ["tasks"],
                "icon": resolved_icon,
                "avatar_color": resolved_color,
                "config": {
                    "meson": True,
                    "department": plan.department,
                    "systems": plan.systems,
                    "trainingPlan": cfg.training,
                    "personaRole": persona_role,
                    "personality": personality,
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
                from app.workflows.schema_sync import mirror_legacy_workflow_row_to_contract

                mirror_legacy_workflow_row_to_contract(client, dict(created.data[0]))
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

        blob = " ".join(
            f"{n.get('type') or ''} {n.get('name') or ''} {n.get('vendor') or ''}".lower()
            for n in nodes
        )
        is_enrichment = (
            "apollo" in blob and "clay" in blob and ("hubspot" in blob or "hubs" in blob)
        )

        # Enrichment canvases need setup / connector guidance — not generic Slack gates.
        if is_enrichment:
            agent_nodes = [n for n in nodes if str(n.get("type") or "") == "agent"]
            unbound = [
                n
                for n in agent_nodes
                if not str(
                    (n.get("config") or {}).get("agent_id")
                    or (n.get("config") or {}).get("agentId")
                    or n.get("agent_id")
                    or ""
                ).strip()
            ]
            thin = [
                n
                for n in nodes
                if len(
                    str(
                        (n.get("config") or {}).get("task")
                        or (n.get("config") or {}).get("instruction")
                        or n.get("description")
                        or ""
                    ).strip()
                )
                < 40
            ]
            if unbound or thin:
                suggestions.append(
                    MesonSuggestion(
                        id="setup-enrichment-workflow",
                        nodeType="agent",
                        label="Set up enrichment agents & instructions",
                        reason=(
                            "Bind Lead Enrichment Coordinator and fill Apollo → Clay → HubSpot "
                            "task instructions so this workflow can run end-to-end."
                        ),
                        confidence=0.94,
                        confidenceIsEstimate=True,
                        confidenceSource="canvas-enrichment",
                    )
                )
            if "apollo" in blob:
                suggestions.append(
                    MesonSuggestion(
                        id="tip-enrichment-apollo-list",
                        nodeType="connector",
                        label="Confirm Apollo list name",
                        reason=(
                            'Use list "MSP Prospects" (or APOLLO_LIST_NAME) before Clay push — '
                            "empty lists should be populated by the agent step."
                        ),
                        confidence=0.86,
                        confidenceIsEstimate=True,
                        confidenceSource="canvas-enrichment",
                    )
                )
            if "hubspot" in blob or "hubs" in blob:
                suggestions.append(
                    MesonSuggestion(
                        id="tip-enrichment-hubspot-list",
                        nodeType="agent",
                        label="Set HubSpot list ID",
                        reason=(
                            "Install variable HUBSPOT_LIST_ID must point at the existing "
                            '"MSPs" static list before list-membership runs.'
                        ),
                        confidence=0.84,
                        confidenceIsEstimate=True,
                        confidenceSource="canvas-enrichment",
                    )
                )
            suggestions.append(
                MesonSuggestion(
                    id="tip-enrichment-preview",
                    nodeType="task",
                    label="Dry-run before production",
                    reason=(
                        "Preview this enrichment path once connectors are connected — "
                        "verify Clay outputs map into HubSpot contacts."
                    ),
                    confidence=0.8,
                    confidenceIsEstimate=True,
                    confidenceSource="canvas-enrichment",
                )
            )
            filtered = [s for s in suggestions if s.id not in dismissed]
            ranked = _rank_suggestions_by_feedback(filtered, feedback_summary)
            return MesonSuggestionsResponse(suggestions=_rotate_suggestions(ranked, org_id)[:5])

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

        # Canvas-aware tips that rotate so Meson does not feel static.
        tip_pool = _canvas_tip_suggestions(nodes, last_added_node)
        suggestions.extend(tip_pool)

        filtered = [s for s in suggestions if s.id not in dismissed]
        ranked = _rank_suggestions_by_feedback(filtered, feedback_summary)
        return MesonSuggestionsResponse(suggestions=_rotate_suggestions(ranked, org_id)[:5])

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

        # Apply/Review must hide the card platform-wide (Optimize + Alerts + page context).
        acknowledged_ids = set(dismissed_ids)
        for suggestion_id, counts in by_suggestion.items():
            if int(counts.get("accepted") or 0) > 0:
                acknowledged_ids.add(str(suggestion_id))

        return {
            "dismissed_ids": dismissed_ids,
            "acknowledged_ids": acknowledged_ids,
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
        feedback_summary: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        canvas_vendors: set[str] | None = None,
    ) -> MesonAlertsResponse:
        alerts: list[MesonAlert] = []
        acknowledged = _acknowledged_ids(feedback_summary)
        scoped_workflow_id = (workflow_id or "").strip() or None
        vendors = {v.lower() for v in (canvas_vendors or set()) if v}

        from app.intelligence_packs.shared.auth_mode import is_knowledge_base_source
        from app.services.workflow_failure_prediction_service import dismiss_failure_alert

        failure_kwargs: dict[str, Any] = {"status": "open", "limit": 20}
        if scoped_workflow_id:
            failure_kwargs["workflow_id"] = scoped_workflow_id

        for row in list_failure_alerts(client, org_id, **failure_kwargs):
            evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
            connector_type = str(
                evidence.get("connectorType") or evidence.get("connector_type") or ""
            ).strip()
            alert_type = str(row.get("alertType") or row.get("alert_type") or "")
            # Stale rows from before knowledge-base packs were excluded from connector_missing.
            if alert_type == "connector_missing" and connector_type and is_knowledge_base_source(
                connector_type
            ):
                alert_id = str(row.get("id") or "")
                if alert_id:
                    try:
                        dismiss_failure_alert(client, org_id, alert_id)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("meson dismiss stale kb alert skipped: %s", exc)
                continue

            row_workflow_id = str(row.get("workflowId") or row.get("workflow_id") or "")
            if scoped_workflow_id and row_workflow_id and row_workflow_id != scoped_workflow_id:
                continue
            connector_id = str(row.get("connectorId") or row.get("connector_id") or "").strip()
            action_target = (
                f"/workflows/{row_workflow_id}/builder" if row_workflow_id else "/metrics"
            )
            fix_label = "Review"
            if alert_type == "connector_missing" and connector_type:
                from app.intelligence_packs.shared.auth_mode import canonical_connector_vendor

                canon = canonical_connector_vendor(connector_type) or connector_type
                if vendors and canon.lower() not in vendors and connector_type.lower() not in vendors:
                    continue
                action_target = f"/connectors?type={canon}"
                fix_label = "Connect"
            elif alert_type in {"auth_disconnected", "auth_expiry"} and connector_id:
                action_target = f"/connectors/{connector_id}"
                fix_label = "Reconnect"
            alerts.append(
                MesonAlert(
                    id=str(row.get("id") or f"failure-{len(alerts)}"),
                    severity=str(row.get("severity") or "warning"),
                    title=str(row.get("title") or "Workflow risk detected"),
                    message=str(row.get("message") or "Review predicted failure before next run."),
                    autoFixable=True,
                    actionType="navigate",
                    actionTarget=action_target,
                    fixLabel=fix_label,
                )
            )

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            failed_q = (
                client.table("workflow_runs")
                .select("id, workflow_id, error_message, created_at")
                .eq("org_id", org_id)
                .eq("environment", environment_name)
                .eq("status", "failed")
                .gte("created_at", cutoff)
                .order("created_at", desc=True)
                .limit(10)
            )
            if scoped_workflow_id:
                failed_q = failed_q.eq("workflow_id", scoped_workflow_id)
            failed_runs = failed_q.execute()
            from app.services.gravitree_voice import format_operator_message

            for run in failed_runs.data or []:
                run_id = str(run.get("id") or "")
                if any(a.id == f"run-failed-{run_id}" for a in alerts):
                    continue
                raw = str(run.get("error_message") or "").strip()
                # Pass through voice-shaped gate/execute errors; otherwise shape blocked.
                if raw and (
                    "Write blocked" in raw
                    or "not Connected" in raw
                    or raw.startswith("Blocked.")
                ):
                    message = raw
                else:
                    message = format_operator_message(
                        "blocked",
                        blocker=raw or "A workflow run failed recently.",
                        next_action="Open the run, fix the blocker, then retry.",
                        confidence_register="blocked",
                        allow_humor=False,
                    )
                alerts.append(
                    MesonAlert(
                        id=f"run-failed-{run_id}",
                        severity="critical",
                        title="Recent workflow failure",
                        message=message[:500],
                        autoFixable=True,
                        actionType="navigate",
                        actionTarget=f"/runs/{run_id}",
                        fixLabel="View run",
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
                if vendors and vendor.lower() not in vendors:
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
                            actionType="navigate",
                            actionTarget=f"/connectors/{connector_id}",
                            fixLabel="Reconnect",
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson alerts connector lookup: %s", exc)

        if acknowledged:
            alerts = [a for a in alerts if a.id not in acknowledged]
        return MesonAlertsResponse(alerts=alerts[:20])

    def get_proactive_insights(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
        feedback_summary: dict[str, Any] | None = None,
    ) -> MesonInsightsResponse:
        insights: list[MesonInsight] = []
        acknowledged = _acknowledged_ids(feedback_summary)

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

        try:
            pending_business = (
                client.table("optimization_suggestions")
                .select("suggestion_type")
                .eq("org_id", org_id)
                .eq("status", "pending_review")
                .in_(
                    "suggestion_type",
                    ["stalled_deal", "overdue_invoice", "support_backlog_growth"],
                )
                .limit(10)
                .execute()
            )
            business_rows = pending_business.data if isinstance(pending_business.data, list) else []
            if business_rows:
                types = sorted({str(r.get("suggestion_type") or "") for r in business_rows})
                insights.append(
                    MesonInsight(
                        id="business-signals-pending",
                        title="Business signals awaiting review",
                        summary=(
                            f"{len(business_rows)} proactive business signal(s) "
                            f"({', '.join(t.replace('_', ' ') for t in types)}) need operator review."
                        ),
                        category="business",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson insights business signals lookup: %s", exc)

        if acknowledged:
            insights = [i for i in insights if i.id not in acknowledged]

        if not insights and "meson-ready" not in acknowledged:
            insights.append(
                MesonInsight(
                    id="meson-ready",
                    title="Meson is monitoring your workspace",
                    summary="No urgent issues detected. Keep building — Meson will suggest next steps as you add nodes.",
                    category="general",
                )
            )

        return MesonInsightsResponse(insights=insights[:10])

    def get_page_context(
        self,
        client: Any,
        org_id: str,
        *,
        page: str,
        entity_id: str | None = None,
        environment_name: str,
        feedback_summary: dict[str, Any] | None = None,
    ) -> MesonPageContextResponse:
        """Return Meson insights and suggestions scoped to a product surface."""
        acknowledged = _acknowledged_ids(feedback_summary)
        normalized = (page or "").strip().lower().replace("_", "-")
        if normalized == "ai-chat":
            result = self._page_context_ai_chat(client, org_id, environment_name=environment_name)
        elif normalized == "model-registry":
            result = self._page_context_model_registry(client, org_id, entity_id=entity_id)
        elif normalized in {"model-detail", "model-detail-page"}:
            result = self._page_context_model_detail(client, org_id, entity_id=entity_id)
        elif normalized in {"agent-detail", "agent-detail-page"}:
            result = self._page_context_agent_detail(client, org_id, entity_id=entity_id)
        elif normalized == "connectors":
            result = self._page_context_connectors(client, org_id, environment_name=environment_name)
        elif normalized in {"workflows", "workflow-detail", "workflow-detail-page"}:
            result = self._page_context_workflows(
                client, org_id, entity_id=entity_id, environment_name=environment_name
            )
        elif normalized == "agents":
            result = self._page_context_agents_list(client, org_id, environment_name=environment_name)
        elif normalized == "training":
            result = self._page_context_training(client, org_id)
        elif normalized == "intelligence":
            result = self._page_context_intelligence(client, org_id, environment_name=environment_name)
        elif normalized in {"multi-agent-run", "multi-agent", "swarm"}:
            result = self._page_context_multi_agent(client, org_id, environment_name=environment_name)
        elif normalized == "marketplace":
            result = self._page_context_marketplace(client, org_id)
        elif normalized == "runs":
            result = self._page_context_runs(client, org_id, environment_name=environment_name)
        elif normalized in {"failure-alerts", "failure-predictions"}:
            result = self._page_context_failure_alerts(client, org_id)
        elif normalized == "home":
            result = self._page_context_home(client, org_id, environment_name=environment_name)
        elif normalized == "metrics":
            result = self._page_context_metrics(client, org_id, environment_name=environment_name)
        elif normalized in {"schedules", "schedule", "calendar"}:
            result = self._page_context_schedules(
                client, org_id, entity_id=entity_id, environment_name=environment_name
            )
        else:
            base = self.get_proactive_insights(
                client,
                org_id,
                environment_name=environment_name,
                feedback_summary=feedback_summary,
            )
            result = MesonPageContextResponse(
                insights=base.insights[:5],
                suggestions=[],
                source="general",
            )

        if acknowledged:
            result = MesonPageContextResponse(
                insights=[i for i in result.insights if i.id not in acknowledged],
                suggestions=[s for s in result.suggestions if s.id not in acknowledged],
                source=result.source,
            )
        return result

    def _page_context_ai_chat(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
    ) -> MesonPageContextResponse:
        insights_resp = self.get_proactive_insights(client, org_id, environment_name=environment_name)
        insights = insights_resp.insights[:4]
        suggestions: list[MesonSuggestion] = []

        try:
            connectors = list_connectors(client, org_id, environment_name=environment_name)
            auth_issues = [
                c for c in connectors if resolve_connector_auth_status(c).needs_reauth
            ]
            if auth_issues:
                names = ", ".join(
                    str(c.get("name") or c.get("type") or "connector") for c in auth_issues[:3]
                )
                insights.insert(
                    0,
                    MesonInsight(
                        id="connectors-auth",
                        title="Connectors need authentication",
                        summary=f"{len(auth_issues)} connector(s) require re-auth ({names}).",
                        category="operations",
                    ),
                )
                suggestions.append(
                    MesonSuggestion(
                        id="fix-connectors",
                        nodeType="navigate",
                        label="Review connector health",
                        reason="Restore data access before delegating tasks.",
                        confidence=0.88,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson ai-chat connector lookup: %s", exc)

        try:
            recent_runs = (
                client.table("workflow_runs")
                .select("id, status, workflow_id")
                .eq("org_id", org_id)
                .eq("environment", environment_name)
                .order("created_at", desc=True)
                .limit(8)
                .execute()
            )
            completed = [
                r for r in (recent_runs.data or []) if str(r.get("status") or "") in {"completed", "success"}
            ]
            if completed:
                suggestions.append(
                    MesonSuggestion(
                        id="summarize-runs",
                        nodeType="chat",
                        label="Summarize recent agent work",
                        reason=f"{len(completed)} task(s) completed recently — ask for a recap.",
                        confidence=0.72,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson ai-chat run lookup: %s", exc)

        if not suggestions:
            suggestions.append(
                MesonSuggestion(
                    id="delegate-task",
                    nodeType="chat",
                    label="Delegate a recurring workflow",
                    reason="Switch to Execute mode to assign operational work to agents.",
                    confidence=0.7,
                )
            )

        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="ai-chat",
        )

    def _page_context_connectors(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
    ) -> MesonPageContextResponse:
        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []
        try:
            connectors = list_connectors(client, org_id, environment_name=environment_name)
            auth_issues = [c for c in connectors if resolve_connector_auth_status(c).needs_reauth]
            healthy = len(connectors) - len(auth_issues)
            if auth_issues:
                names = ", ".join(
                    str(c.get("name") or c.get("type") or "connector") for c in auth_issues[:3]
                )
                insights.append(
                    MesonInsight(
                        id="connectors-auth",
                        title="Connectors need authentication",
                        summary=f"{len(auth_issues)} integration(s) require re-auth ({names}).",
                        category="operations",
                    )
                )
                suggestions.append(
                    MesonSuggestion(
                        id="fix-connectors",
                        nodeType="navigate",
                        label="Fix connector authentication",
                        reason="Restore OAuth tokens before workflows can read or write data.",
                        confidence=0.9,
                    )
                )
            elif not connectors:
                suggestions.append(
                    MesonSuggestion(
                        id="add-connector",
                        nodeType="navigate",
                        label="Connect your first tool",
                        reason="Link CRM, messaging, or dev systems so agents can act on live data.",
                        confidence=0.85,
                    )
                )
            else:
                insights.append(
                    MesonInsight(
                        id="connectors-healthy",
                        title=f"{healthy} connector(s) active",
                        summary="Run periodic health checks to catch scope or token drift early.",
                        category="operations",
                    )
                )
                suggestions.append(
                    MesonSuggestion(
                        id="test-connectors",
                        nodeType="navigate",
                        label="Run connector health checks",
                        reason="Validate OAuth scopes and API reachability across your stack.",
                        confidence=0.78,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson connectors page context: %s", exc)
        if not insights:
            insights.append(
                MesonInsight(
                    id="connectors-monitor",
                    title="Meson is watching integrations",
                    summary="Connect tools to unlock workflow automation and agent tool calls.",
                    category="operations",
                )
            )
        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="connectors",
        )

    def _page_context_workflows(
        self,
        client: Any,
        org_id: str,
        *,
        entity_id: str | None,
        environment_name: str,
    ) -> MesonPageContextResponse:
        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []
        if entity_id:
            opt = self.get_workflow_optimizations(
                client, org_id, entity_id, environment_name=environment_name
            )
            insights.extend(opt.insights[:3])
            suggestions.append(
                MesonSuggestion(
                    id="open-builder",
                    nodeType="navigate",
                    label="Open workflow builder",
                    reason="Review steps, simulate runs, and apply Meson optimization hints.",
                    confidence=0.82,
                )
            )
        try:
            workflows = (
                client.table("workflow_defs")
                .select("id, status, name")
                .eq("org_id", org_id)
                .limit(100)
                .execute()
            )
            rows = workflows.data or []
            draft_count = sum(1 for w in rows if str(w.get("status") or "") == "draft")
            if draft_count:
                insights.insert(
                    0,
                    MesonInsight(
                        id="draft-workflows",
                        title="Draft workflows awaiting publish",
                        summary=f"{draft_count} workflow(s) are still in draft — validate before production.",
                        category="workflow",
                    ),
                )
                suggestions.append(
                    MesonSuggestion(
                        id="publish-workflows",
                        nodeType="navigate",
                        label="Review draft workflows",
                        reason="Publish validated flows so schedules and agents can execute them.",
                        confidence=0.8,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson workflows page context: %s", exc)
        open_alerts = list_failure_alerts(client, org_id, status="open", limit=3)
        if open_alerts:
            insights.append(
                MesonInsight(
                    id="failure-alerts",
                    title="Failure predictions open",
                    summary=f"{len(open_alerts)} alert(s) may affect upcoming runs — review risk signals.",
                    category="risk",
                )
            )
            suggestions.append(
                MesonSuggestion(
                    id="review-failure-alerts",
                    nodeType="navigate",
                    label="Review failure alerts",
                    reason="Inspect predicted failures before the next scheduled execution.",
                    confidence=0.86,
                )
            )
        if not suggestions:
            suggestions.append(
                MesonSuggestion(
                    id="simulate-workflow",
                    nodeType="navigate",
                    label="Dry-run a workflow",
                    reason="Simulate steps with live connector checks before enabling schedules.",
                    confidence=0.74,
                )
            )
        if not insights:
            insights.append(
                MesonInsight(
                    id="workflows-ready",
                    title="Build repeatable automations",
                    summary="Combine connectors, approvals, and agent steps into governed workflows.",
                    category="workflow",
                )
            )
        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="workflows",
        )

    def _page_context_agents_list(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
    ) -> MesonPageContextResponse:
        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []
        try:
            resp = (
                client.table("agents")
                .select("id, name, status, stats")
                .eq("org_id", org_id)
                .limit(50)
                .execute()
            )
            agents = resp.data or []
            if not agents:
                suggestions.append(
                    MesonSuggestion(
                        id="create-agent",
                        nodeType="navigate",
                        label="Create your first agent",
                        reason="Define role, tools, and knowledge before delegating work.",
                        confidence=0.88,
                    )
                )
            else:
                low_success = []
                for agent in agents:
                    stats = agent.get("stats") if isinstance(agent.get("stats"), dict) else {}
                    rate = stats.get("successRate") or stats.get("success_rate")
                    if rate is not None and float(rate) < 70:
                        low_success.append(str(agent.get("name") or "Agent"))
                if low_success:
                    insights.append(
                        MesonInsight(
                            id="agents-low-success",
                            title="Agents below success target",
                            summary=f"Review knowledge and tools for: {', '.join(low_success[:3])}.",
                            category="agents",
                        )
                    )
                suggestions.append(
                    MesonSuggestion(
                        id="multi-agent-run",
                        nodeType="navigate",
                        label="Run parallel agents on one objective",
                        reason="Fan out subtasks and merge council recommendations.",
                        confidence=0.76,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson agents list page context: %s", exc)
        if not insights:
            insights.append(
                MesonInsight(
                    id="agents-team",
                    title="Your AI team",
                    summary="Assign agents to workflows, chat, and marketplace role packs.",
                    category="agents",
                )
            )
        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="agents",
        )

    def _page_context_training(
        self,
        client: Any,
        org_id: str,
    ) -> MesonPageContextResponse:
        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []
        try:
            resp = (
                client.table("trained_models")
                .select("id, status")
                .eq("org_id", org_id)
                .limit(100)
                .execute()
            )
            rows = resp.data or []
            training = sum(1 for r in rows if str(r.get("status") or "") in {"training", "pending"})
            if training:
                insights.append(
                    MesonInsight(
                        id="training-jobs",
                        title="Training jobs in flight",
                        summary=f"{training} model job(s) running — outcomes feed Learning signals.",
                        category="learning",
                    )
                )
            elif not rows:
                suggestions.append(
                    MesonSuggestion(
                        id="add-training-data",
                        nodeType="navigate",
                        label="Add training examples",
                        reason="Capture approved agent responses to improve future behavior.",
                        confidence=0.84,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson training page context: %s", exc)
        suggestions.append(
            MesonSuggestion(
                id="review-learning",
                nodeType="navigate",
                label="Review Learning signals",
                reason="See which queries and outcomes are ready to promote to Training.",
                confidence=0.77,
            )
        )
        if not insights:
            insights.append(
                MesonInsight(
                    id="training-loop",
                    title="Shape agent behavior",
                    summary="Examples and fine-tunes change how agents respond on your org data.",
                    category="learning",
                )
            )
        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="training",
        )

    def _page_context_intelligence(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
    ) -> MesonPageContextResponse:
        base = self.get_proactive_insights(client, org_id, environment_name=environment_name)
        insights = list(base.insights[:4])
        suggestions = [
            MesonSuggestion(
                id="open-learning",
                nodeType="navigate",
                label="Inspect Learning trends",
                reason="Verify confidence scores before promoting memories or models.",
                confidence=0.8,
            ),
            MesonSuggestion(
                id="review-reports",
                nodeType="navigate",
                label="Open intelligence reports",
                reason="ROI and department scorecards show measured business impact.",
                confidence=0.75,
            ),
        ]
        if not insights:
            insights.append(
                MesonInsight(
                    id="intelligence-warming",
                    title="Insights are warming up",
                    summary="Run workflows and connect tools to populate trust and maturity signals.",
                    category="learning",
                )
            )
        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="intelligence",
        )

    def _page_context_multi_agent(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
    ) -> MesonPageContextResponse:
        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []
        try:
            resp = (
                client.table("agent_swarm_runs")
                .select("id, status")
                .eq("org_id", org_id)
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
            runs = resp.data or []
            active = sum(
                1 for r in runs if str(r.get("status") or "") in {"pending", "running", "aggregating"}
            )
            if active:
                insights.append(
                    MesonInsight(
                        id="swarm-active",
                        title=f"{active} multi-agent run(s) in progress",
                        summary="Monitor subtasks until the council merges a final recommendation.",
                        category="agents",
                    )
                )
            elif not runs:
                suggestions.append(
                    MesonSuggestion(
                        id="start-swarm",
                        nodeType="navigate",
                        label="Start your first multi-agent run",
                        reason="Split one objective across parallel agents, then merge results.",
                        confidence=0.86,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson multi-agent page context: %s", exc)
        suggestions.append(
            MesonSuggestion(
                id="configure-agents",
                nodeType="navigate",
                label="Configure parent agents",
                reason="Specialized agents produce better parallel subtask outputs.",
                confidence=0.78,
            )
        )
        if not insights:
            insights.append(
                MesonInsight(
                    id="swarm-overview",
                    title="Parallel agent coordination",
                    summary="One objective, many agents, one merged recommendation.",
                    category="agents",
                )
            )
        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="multi-agent-run",
        )

    def _page_context_marketplace(
        self,
        client: Any,
        org_id: str,
    ) -> MesonPageContextResponse:
        insights = [
            MesonInsight(
                id="marketplace-discover",
                title="Extend your stack from Marketplace",
                summary="Install agent packs, workflows, and connector bundles vetted for your org.",
                category="marketplace",
            )
        ]
        suggestions = [
            MesonSuggestion(
                id="browse-assets",
                nodeType="navigate",
                label="Browse unified assets",
                reason="Filter by department, connector coverage, and install readiness.",
                confidence=0.8,
            ),
            MesonSuggestion(
                id="installed-assets",
                nodeType="navigate",
                label="Review installed assets",
                reason="Confirm entitlements and rollback paths after each install.",
                confidence=0.72,
            ),
        ]
        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="marketplace",
        )

    def _page_context_runs(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
    ) -> MesonPageContextResponse:
        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []
        try:
            resp = (
                client.table("workflow_runs")
                .select("id, status")
                .eq("org_id", org_id)
                .eq("environment", environment_name)
                .order("created_at", desc=True)
                .limit(30)
                .execute()
            )
            rows = resp.data or []
            failed = [r for r in rows if str(r.get("status") or "") in {"failed", "error"}]
            running = [r for r in rows if str(r.get("status") or "") in {"running", "pending", "approved"}]
            if failed:
                insights.append(
                    MesonInsight(
                        id="recent-failures",
                        title="Recent failed runs",
                        summary=f"{len(failed)} failure(s) in the last {len(rows)} runs — inspect step logs.",
                        category="reliability",
                    )
                )
                suggestions.append(
                    MesonSuggestion(
                        id="investigate-failures",
                        nodeType="navigate",
                        label="Open latest failed run",
                        reason="Retry steps or adjust connector scopes before re-running.",
                        confidence=0.85,
                    )
                )
            if running:
                insights.insert(
                    0,
                    MesonInsight(
                        id="runs-active",
                        title=f"{len(running)} run(s) in progress",
                        summary="Pause or cancel from run detail if execution needs review.",
                        category="activity",
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson runs page context: %s", exc)
        if not suggestions:
            suggestions.append(
                MesonSuggestion(
                    id="summarize-runs",
                    nodeType="navigate",
                    label="Ask Chat to summarize runs",
                    reason="Get a plain-English recap of recent execution outcomes.",
                    confidence=0.7,
                )
            )
        if not insights:
            insights.append(
                MesonInsight(
                    id="runs-empty",
                    title="Execution timeline",
                    summary="Workflow and agent runs appear here with status, duration, and audit trail.",
                    category="activity",
                )
            )
        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="runs",
        )

    def _page_context_schedules(
        self,
        client: Any,
        org_id: str,
        *,
        entity_id: str | None,
        environment_name: str,
    ) -> MesonPageContextResponse:
        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []

        try:
            schedules = list_org_workflow_schedules(
                client,
                org_id,
                environment_name=environment_name,
                workflow_id=entity_id,
            )
            disabled = [
                row
                for row in schedules
                if not bool(row.get("is_enabled", row.get("enabled", True)))
            ]
            if disabled:
                insights.append(
                    MesonInsight(
                        id="schedules-disabled",
                        title="Disabled workflow schedules",
                        summary=f"{len(disabled)} recurring schedule(s) are paused — re-enable or delete them to avoid confusion.",
                        category="operations",
                    )
                )
                suggestions.append(
                    MesonSuggestion(
                        id="review-disabled-schedules",
                        nodeType="navigate",
                        label="Review paused schedules",
                        reason="Clean up stale cron entries before the next production window.",
                        confidence=0.82,
                    )
                )
            elif schedules:
                from app.services.schedules_aggregation_service import (
                    default_projection_window,
                    list_scheduled_items,
                )

                window_start, window_end = default_projection_window()
                projected = list_scheduled_items(
                    client,
                    org_id,
                    environment_name,
                    workflow_id=entity_id,
                    window_start=window_start,
                    window_end=window_end,
                    kinds=frozenset({"workflow"}),
                )
                upcoming_bits: list[str] = []
                for item in projected[:5]:
                    occs = list(item.get("occurrences") or [])
                    next_at = occs[0] if occs else item.get("nextRunAt")
                    if next_at:
                        upcoming_bits.append(f"{item.get('title') or 'Workflow'} @ {next_at}")
                summary = "Drag items on the calendar or use the popup to reschedule, edit, or delete."
                if upcoming_bits:
                    summary = "Upcoming: " + "; ".join(upcoming_bits[:3]) + ". " + summary
                insights.append(
                    MesonInsight(
                        id="schedules-active",
                        title=f"{len(schedules)} workflow schedule(s) active",
                        summary=summary[:500],
                        category="operations",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson schedules workflow lookup: %s", exc)

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
                    insights.insert(
                        0,
                        MesonInsight(
                            id="schedule-run-success-rate",
                            title="Run success rate below target",
                            summary=f"Recent success rate is {rate}% — review failing steps and connector health before the next scheduled run.",
                            category="reliability",
                        ),
                    )
                    suggestions.append(
                        MesonSuggestion(
                            id="inspect-scheduled-failures",
                            nodeType="navigate",
                            label="Review recent failed runs",
                            reason="Scheduled tasks may keep failing until root causes are fixed.",
                            confidence=0.86,
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson schedules run lookup: %s", exc)

        try:
            queued_runs = (
                client.table("workflow_runs")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("environment", environment_name)
                .in_("status", ["pending", "pending_approval", "approved", "queued"])
                .limit(1)
                .execute()
            )
            queued_count = int(getattr(queued_runs, "count", None) or len(queued_runs.data or []))
            if queued_count:
                insights.append(
                    MesonInsight(
                        id="schedules-queued-tasks",
                        title=f"{queued_count} task run(s) queued",
                        summary="Open a task from the calendar to reschedule or cancel before it starts.",
                        category="activity",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson schedules queued lookup: %s", exc)

        if entity_id:
            suggestions.append(
                MesonSuggestion(
                    id="workflow-schedule-create",
                    nodeType="navigate",
                    label="Add another schedule for this workflow",
                    reason="Keep recurring automation aligned with business hours.",
                    confidence=0.74,
                )
            )
        else:
            suggestions.append(
                MesonSuggestion(
                    id="filter-schedule-types",
                    nodeType="navigate",
                    label="Filter by task or training job",
                    reason="Focus the calendar on the schedule types you are tuning today.",
                    confidence=0.7,
                )
            )

        if not insights:
            insights.append(
                MesonInsight(
                    id="schedules-overview",
                    title="Unified schedule calendar",
                    summary="Workflow crons, task runs, and training jobs appear here — click any item to move, edit, or delete.",
                    category="operations",
                )
            )

        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="schedules",
        )

    def _page_context_failure_alerts(
        self,
        client: Any,
        org_id: str,
    ) -> MesonPageContextResponse:
        open_alerts = list_failure_alerts(client, org_id, status="open", limit=10)
        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []
        if open_alerts:
            insights.append(
                MesonInsight(
                    id="open-alerts",
                    title=f"{len(open_alerts)} open failure prediction(s)",
                    summary="Review connector auth, rate limits, and historical failures before the next run.",
                    category="risk",
                )
            )
            suggestions.append(
                MesonSuggestion(
                    id="triage-alerts",
                    nodeType="navigate",
                    label="Triage highest-risk alerts",
                    reason="Resolve or snooze predictions tied to production workflows.",
                    confidence=0.88,
                )
            )
        else:
            insights.append(
                MesonInsight(
                    id="alerts-clear",
                    title="No open failure alerts",
                    summary="Predictive scans will surface new risks when run history shifts.",
                    category="risk",
                )
            )
        suggestions.append(
            MesonSuggestion(
                id="scan-workflows",
                nodeType="navigate",
                label="Scan workflows for risk",
                reason="Run failure prediction across active workflow definitions.",
                confidence=0.76,
            )
        )
        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="failure-alerts",
        )

    def _page_context_home(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
    ) -> MesonPageContextResponse:
        base = self.get_proactive_insights(client, org_id, environment_name=environment_name)
        suggestions = [
            MesonSuggestion(
                id="open-chat",
                nodeType="navigate",
                label="Open Chat to delegate work",
                reason="Route execute, search, and Q&A from one surface.",
                confidence=0.82,
            ),
            MesonSuggestion(
                id="check-connectors-home",
                nodeType="navigate",
                label="Verify connector health",
                reason="Healthy integrations unblock workflows and agent tool calls.",
                confidence=0.78,
            ),
        ]
        return MesonPageContextResponse(
            insights=base.insights[:4],
            suggestions=suggestions[:4],
            source="home",
        )

    def _page_context_metrics(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
    ) -> MesonPageContextResponse:
        base = self.get_proactive_insights(client, org_id, environment_name=environment_name)
        suggestions = [
            MesonSuggestion(
                id="metrics-anomalies",
                nodeType="navigate",
                label="Investigate throughput dips",
                reason="Correlate run volume changes with connector or workflow edits.",
                confidence=0.74,
            ),
        ]
        return MesonPageContextResponse(
            insights=base.insights[:4],
            suggestions=suggestions[:4],
            source="metrics",
        )

    def _page_context_model_registry(
        self,
        client: Any,
        org_id: str,
        *,
        entity_id: str | None,
    ) -> MesonPageContextResponse:
        if entity_id:
            return self._page_context_model_detail(client, org_id, entity_id=entity_id)

        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []
        rows: list[dict[str, Any]] = []

        try:
            resp = (
                client.table("trained_models")
                .select("id, name, status, model_type, deployed_version, current_version, dataset_id")
                .eq("org_id", org_id)
                .limit(200)
                .execute()
            )
            rows = resp.data or []
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson model registry lookup: %s", exc)

        if not rows:
            return MesonPageContextResponse(
                insights=[
                    MesonInsight(
                        id="no-models",
                        title="Start your model registry",
                        summary="Register a classifier, forecaster, or fine-tuned LLM to wire ML into workflows.",
                        category="ml",
                    )
                ],
                suggestions=[
                    MesonSuggestion(
                        id="register-first-model",
                        nodeType="navigate",
                        label="Register your first model",
                        reason="Pick a template from the ML stack layers to get started.",
                        confidence=0.85,
                    )
                ],
                source="model-registry",
            )

        status_counts: dict[str, int] = {}
        for row in rows:
            key = str(row.get("status") or "draft")
            status_counts[key] = status_counts.get(key, 0) + 1

        deployed = status_counts.get("deployed", 0)
        training = status_counts.get("training", 0) + status_counts.get("validating", 0)
        ready = status_counts.get("ready", 0)
        failed = status_counts.get("failed", 0)

        if training:
            insights.append(
                MesonInsight(
                    id="models-training",
                    title=f"{training} model(s) in training",
                    summary="Monitor validation metrics before promoting to production deploy.",
                    category="ml",
                )
            )
        if ready and not deployed:
            insights.append(
                MesonInsight(
                    id="models-ready-not-deployed",
                    title="Ready models awaiting deploy",
                    summary=f"{ready} model(s) passed validation but are not live in production yet.",
                    category="ml",
                )
            )
        if failed:
            insights.append(
                MesonInsight(
                    id="models-failed",
                    title="Training failures detected",
                    summary=f"{failed} model(s) failed — review dataset quality and hyperparameters.",
                    category="ml",
                )
            )
        without_dataset = sum(1 for r in rows if not r.get("dataset_id"))
        if without_dataset:
            suggestions.append(
                MesonSuggestion(
                    id="link-datasets",
                    nodeType="navigate",
                    label="Link training datasets",
                    reason=f"{without_dataset} registered model(s) have no dataset — connect from Training.",
                    confidence=0.8,
                )
            )
        if ready:
            suggestions.append(
                MesonSuggestion(
                    id="deploy-ready-models",
                    nodeType="navigate",
                    label="Deploy validated models",
                    reason="Promote ready versions to production inference endpoints.",
                    confidence=0.82,
                )
            )

        if not insights:
            insights.append(
                MesonInsight(
                    id="registry-healthy",
                    title="Registry looks healthy",
                    summary=f"{len(rows)} model(s) tracked — {deployed} deployed to production.",
                    category="ml",
                )
            )

        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="model-registry",
        )

    def _page_context_model_detail(
        self,
        client: Any,
        org_id: str,
        *,
        entity_id: str | None,
    ) -> MesonPageContextResponse:
        if not entity_id:
            return self._page_context_model_registry(client, org_id, entity_id=None)

        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []
        model: dict[str, Any] | None = None

        try:
            resp = (
                client.table("trained_models")
                .select(
                    "id, name, status, model_type, deployed_version, current_version, dataset_id, base_model, task_type"
                )
                .eq("org_id", org_id)
                .eq("id", entity_id)
                .limit(1)
                .execute()
            )
            model = (resp.data or [None])[0]
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson model detail lookup: %s", exc)

        if not model:
            return MesonPageContextResponse(
                insights=[
                    MesonInsight(
                        id="model-not-found",
                        title="Model not found",
                        summary="This registry entry may have been archived or removed.",
                        category="ml",
                    )
                ],
                suggestions=[],
                source="model-detail",
            )

        name = str(model.get("name") or "This model")
        status = str(model.get("status") or "draft")
        current_version = int(model.get("current_version") or 0)
        deployed_version = model.get("deployed_version")

        if status == "draft" and current_version == 0:
            insights.append(
                MesonInsight(
                    id="model-needs-training",
                    title="Training not started",
                    summary=f"{name} is registered but has no trained versions yet.",
                    category="ml",
                )
            )
            suggestions.append(
                MesonSuggestion(
                    id="start-training",
                    nodeType="navigate",
                    label="Start a training job",
                    reason="Link a dataset and launch training from the Training surface.",
                    confidence=0.86,
                )
            )
        elif status in {"ready", "deployed"} and deployed_version is None:
            insights.append(
                MesonInsight(
                    id="model-ready-deploy",
                    title="Ready for production deploy",
                    summary=f"Version v{current_version} validated — deploy to enable workflow inference.",
                    category="ml",
                )
            )
            suggestions.append(
                MesonSuggestion(
                    id="deploy-model",
                    nodeType="action",
                    label="Deploy latest version",
                    reason="Activate this model for production inference calls.",
                    confidence=0.84,
                )
            )
        elif status == "deployed":
            insights.append(
                MesonInsight(
                    id="model-live",
                    title="Live in production",
                    summary=f"{name} v{deployed_version} is serving inference — monitor drift via Org Learning.",
                    category="ml",
                )
            )
            suggestions.append(
                MesonSuggestion(
                    id="run-inference-test",
                    nodeType="action",
                    label="Run inference smoke test",
                    reason="Validate latency and output quality on a sample payload.",
                    confidence=0.75,
                )
            )

        if not model.get("dataset_id"):
            suggestions.append(
                MesonSuggestion(
                    id="attach-dataset",
                    nodeType="navigate",
                    label="Attach a training dataset",
                    reason="Models with linked datasets retrain faster from org learning signals.",
                    confidence=0.78,
                )
            )

        if not insights:
            insights.append(
                MesonInsight(
                    id="model-on-track",
                    title="Model lifecycle on track",
                    summary=f"{name} is in {status.replace('_', ' ')} — Meson will flag drift as usage grows.",
                    category="ml",
                )
            )

        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="model-detail",
        )

    def _page_context_agent_detail(
        self,
        client: Any,
        org_id: str,
        *,
        entity_id: str | None,
    ) -> MesonPageContextResponse:
        if not entity_id:
            return MesonPageContextResponse(
                insights=[
                    MesonInsight(
                        id="select-agent",
                        title="Open an agent profile",
                        summary="Meson surfaces learning insights per agent once you select a teammate.",
                        category="agents",
                    )
                ],
                suggestions=[],
                source="agent-detail",
            )

        insights: list[MesonInsight] = []
        suggestions: list[MesonSuggestion] = []
        agent: dict[str, Any] | None = None

        try:
            resp = (
                client.table("agents")
                .select("id, name, status, role, department, capabilities, permissions, config, stats")
                .eq("org_id", org_id)
                .eq("id", entity_id)
                .limit(1)
                .execute()
            )
            agent = (resp.data or [None])[0]
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson agent detail lookup: %s", exc)

        if not agent:
            return MesonPageContextResponse(
                insights=[
                    MesonInsight(
                        id="agent-not-found",
                        title="Agent not found",
                        summary="This agent may have been removed or you lack access.",
                        category="agents",
                    )
                ],
                suggestions=[],
                source="agent-detail",
            )

        name = str(agent.get("name") or "This agent")
        stats = agent.get("stats") if isinstance(agent.get("stats"), dict) else {}
        success_rate = stats.get("successRate") or stats.get("success_rate")
        tasks_today = stats.get("tasksToday") or stats.get("tasks_today") or 0
        capabilities = agent.get("capabilities") or []
        config = agent.get("config") if isinstance(agent.get("config"), dict) else {}
        ref_folders = config.get("reference_folders") or config.get("referenceFolders") or []

        if success_rate is not None:
            rate = float(success_rate)
            if rate < 70:
                insights.append(
                    MesonInsight(
                        id="agent-low-success",
                        title="Success rate below target",
                        summary=f"{name} is at {rate:.0f}% success — review knowledge and tool permissions.",
                        category="learning",
                    )
                )
                suggestions.append(
                    MesonSuggestion(
                        id="expand-knowledge",
                        nodeType="navigate",
                        label="Add reference knowledge",
                        reason="Ground the agent with department playbooks and examples.",
                        confidence=0.83,
                    )
                )
            elif rate >= 90:
                insights.append(
                    MesonInsight(
                        id="agent-high-success",
                        title="Strong operational performance",
                        summary=f"{name} maintains {rate:.0f}% success — consider cloning patterns to other agents.",
                        category="learning",
                    )
                )

        if not ref_folders:
            suggestions.append(
                MesonSuggestion(
                    id="add-reference-folders",
                    nodeType="navigate",
                    label="Organize reference folders",
                    reason="Structured knowledge improves retrieval quality for this agent.",
                    confidence=0.8,
                )
            )

        if not capabilities:
            insights.append(
                MesonInsight(
                    id="agent-no-capabilities",
                    title="Capabilities not configured",
                    summary=f"{name} has no declared capabilities — define scope before delegating work.",
                    category="agents",
                )
            )

        if tasks_today and int(tasks_today) >= 3:
            suggestions.append(
                MesonSuggestion(
                    id="review-agent-runs",
                    nodeType="navigate",
                    label="Review today's runs",
                    reason=f"{name} completed {int(tasks_today)} task(s) today — inspect outcomes for learning.",
                    confidence=0.74,
                )
            )

        status = str(agent.get("status") or "")
        if status in {"processing", "training"}:
            insights.insert(
                0,
                MesonInsight(
                    id="agent-training",
                    title="Agent training in progress",
                    summary=f"{name} is updating from recent examples — expect improved responses soon.",
                    category="learning",
                ),
            )

        if not insights:
            insights.append(
                MesonInsight(
                    id="agent-monitoring",
                    title="Meson is learning from this agent",
                    summary=f"Org learning signals will refine {name}'s recommendations over time.",
                    category="learning",
                )
            )

        if not suggestions:
            suggestions.append(
                MesonSuggestion(
                    id="chat-with-agent",
                    nodeType="navigate",
                    label="Open agent chat",
                    reason="Test delegation patterns and capture feedback for learning loops.",
                    confidence=0.7,
                )
            )

        return MesonPageContextResponse(
            insights=insights[:5],
            suggestions=suggestions[:4],
            source="agent-detail",
        )

    def get_workflow_optimizations(
        self,
        client: Any,
        org_id: str,
        workflow_id: str,
        *,
        environment_name: str,
        feedback_summary: dict[str, Any] | None = None,
        workflow_state: dict[str, Any] | None = None,
    ) -> MesonInsightsResponse:
        """Return workflow-scoped optimization tips for the Meson copilot panel (F1).

        Returns both Tips (category=tip) and Insights so the UI can rotate each pool.
        """
        insights: list[MesonInsight] = []
        acknowledged = _acknowledged_ids(feedback_summary)
        workflow_name = "This workflow"
        nodes = _parse_workflow_nodes(workflow_state)

        try:
            workflow_resp = (
                client.table("workflow_defs")
                .select("id, name, status, stage")
                .eq("org_id", org_id)
                .eq("id", workflow_id)
                .limit(1)
                .execute()
            )
            workflow = (workflow_resp.data or [None])[0]
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson optimizations workflow lookup: %s", exc)
            workflow = None

        if not workflow:
            return MesonInsightsResponse(
                insights=[
                    MesonInsight(
                        id="workflow-not-found",
                        title="Workflow not found",
                        summary="Save this workflow to receive Meson optimization tips.",
                        category="workflow",
                    )
                ]
            )

        workflow_name = str(workflow.get("name") or workflow_name)
        if str(workflow.get("status") or "") == "draft":
            insights.append(
                MesonInsight(
                    id="publish-this-workflow",
                    title="Publish this workflow",
                    summary=f"{workflow_name} is still in draft — validate and publish when ready.",
                    category="workflow",
                )
            )

        try:
            recent_runs = (
                client.table("workflow_runs")
                .select("status")
                .eq("org_id", org_id)
                .eq("workflow_id", workflow_id)
                .eq("environment", environment_name)
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
            statuses = [str(r.get("status") or "") for r in (recent_runs.data or [])]
            if statuses:
                success = sum(1 for s in statuses if s in {"completed", "success"})
                rate = round(success / len(statuses) * 100)
                if rate < 80:
                    insights.append(
                        MesonInsight(
                            id="workflow-run-success-rate",
                            title="This workflow's success rate is low",
                            summary=f"Recent runs for {workflow_name} succeed {rate}% of the time — review failing steps.",
                            category="reliability",
                        )
                    )
                elif rate >= 95 and len(statuses) >= 3:
                    insights.append(
                        MesonInsight(
                            id="workflow-run-success-rate-good",
                            title="Strong reliability for this workflow",
                            summary=f"{workflow_name} completed successfully in {rate}% of the last {len(statuses)} runs.",
                            category="reliability",
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson optimizations run lookup: %s", exc)

        try:
            open_alerts = list_failure_alerts(
                client,
                org_id,
                workflow_id=workflow_id,
                status="open",
                limit=5,
            )
            if open_alerts:
                insights.append(
                    MesonInsight(
                        id="workflow-failure-alerts",
                        title="Predictive alerts for this workflow",
                        summary=f"{len(open_alerts)} open failure prediction(s) — review before the next run.",
                        category="risk",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson optimizations failure alerts: %s", exc)

        try:
            failed_run = (
                client.table("workflow_runs")
                .select("id, error_message")
                .eq("org_id", org_id)
                .eq("workflow_id", workflow_id)
                .eq("environment", environment_name)
                .eq("status", "failed")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if failed_run.data:
                from app.services.gravitree_voice import format_operator_message

                row = failed_run.data[0]
                run_id = str(row.get("id") or "")
                raw = str(row.get("error_message") or "").strip()
                if raw and (
                    "Write blocked" in raw
                    or "not Connected" in raw
                    or raw.startswith("Blocked.")
                ):
                    message = raw
                else:
                    message = format_operator_message(
                        "blocked",
                        blocker=raw or "Latest run failed.",
                        next_action="Open the run, fix the blocker, then retry.",
                        confidence_register="blocked",
                        allow_humor=False,
                    )
                insights.append(
                    MesonInsight(
                        id=f"workflow-last-failed-{run_id}" if run_id else "workflow-last-failed",
                        title="Latest run failed",
                        summary=message[:500],
                        category="reliability",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meson optimizations failed run lookup: %s", exc)

        # Tip + insight pools (rotated) so Optimize is not the same two cards forever.
        tip_pool, insight_pool = _workflow_tip_and_insight_pools(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            nodes=nodes,
            base_insights=insights,
        )
        if acknowledged:
            tip_pool = [i for i in tip_pool if i.id not in acknowledged]
            insight_pool = [i for i in insight_pool if i.id not in acknowledged]

        if not tip_pool and not insight_pool and "meson-workflow-ready" not in acknowledged:
            from app.services.gravitree_voice import format_operator_message

            insight_pool.append(
                MesonInsight(
                    id="meson-workflow-ready",
                    title="Meson is watching this workflow",
                    summary=format_operator_message(
                        "success_win",
                        allow_humor=True,
                        confidence_register="certain",
                    )
                    + " No urgent optimizations — keep building; Meson will suggest next steps as you add nodes.",
                    category="insight",
                )
            )

        seed = _rotation_seed(f"{org_id}:{workflow_id}")
        rotated_tips = _rotate_list(tip_pool, seed, take=2)
        rotated_insights = _rotate_list(insight_pool, seed + 41, take=2)
        # Tips first, then insights — UI splits by category.
        return MesonInsightsResponse(insights=[*rotated_tips, *rotated_insights][:6])

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
        "acknowledged_ids": set(),
        "by_suggestion": {},
        "accepted_count": 0,
        "dismissed_count": 0,
    }


def _acknowledged_ids(feedback_summary: dict[str, Any] | None) -> set[str]:
    if not feedback_summary:
        return set()
    acknowledged = set(feedback_summary.get("acknowledged_ids") or set())
    if not acknowledged:
        # Backward-compatible: older callers may only pass dismissed_ids.
        acknowledged.update(feedback_summary.get("dismissed_ids") or set())
    return {str(x) for x in acknowledged if x}


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
        is_estimate = True
        source = "heuristic"
        if total >= 2:
            rate = accepted / total
            if rate <= 0.25 and dismissed >= 2:
                continue
            # Real acceptance rate over recorded feedback — not a silent constant.
            confidence = min(0.99, max(0.05, rate))
            is_estimate = False
            source = "feedback_acceptance_rate"

        if (
            confidence != suggestion.confidence
            or is_estimate != suggestion.confidence_is_estimate
            or source != suggestion.confidence_source
        ):
            suggestion = suggestion.model_copy(
                update={
                    "confidence": confidence,
                    "confidence_is_estimate": is_estimate,
                    "confidence_source": source,
                }
            )
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


def _rotation_seed(key: str) -> int:
    """Hourly-stable seed so tips/insights rotate without flickering every render."""
    hour = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    raw = f"{key}:{hour}"
    h = 0
    for ch in raw:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def _rotate_list(items: list[Any], seed: int, *, take: int) -> list[Any]:
    if not items or take <= 0:
        return []
    start = seed % len(items)
    out: list[Any] = []
    for i in range(min(take, len(items))):
        out.append(items[(start + i) % len(items)])
    return out


def _rotate_suggestions(suggestions: list[MesonSuggestion], org_id: str) -> list[MesonSuggestion]:
    """Keep high-priority setup suggestions first; rotate the rest hourly."""
    if len(suggestions) <= 2:
        return suggestions
    priority = [s for s in suggestions if s.id.startswith("setup-")]
    rest = [s for s in suggestions if not s.id.startswith("setup-")]
    return [*priority, *_rotate_list(rest, _rotation_seed(org_id), take=len(rest))]


def _canvas_tip_suggestions(
    nodes: list[dict[str, Any]],
    last_added_node: dict[str, Any] | None,
) -> list[MesonSuggestion]:
    """Dynamic tip-style suggestions that vary with canvas shape."""
    tips: list[MesonSuggestion] = []
    types = {str(n.get("type") or "").lower() for n in nodes}
    vendors = {str(n.get("vendor") or "").lower() for n in nodes if n.get("vendor")}
    names = " ".join(str(n.get("name") or "").lower() for n in nodes)
    last_name = str((last_added_node or {}).get("name") or "").strip()

    if "agent" in types and "approval" not in types and len(nodes) >= 3:
        tips.append(
            MesonSuggestion(
                id="tip-human-checkpoint",
                nodeType="approval",
                label="Add a human checkpoint",
                reason="Agent steps can drift — a Quality Gate before writes reduces bad CRM updates.",
                confidence=0.72,
                confidenceIsEstimate=True,
                confidenceSource="canvas-tip",
            )
        )
    if vendors & {"gmail", "outlook", "slack"} and "decision" not in types:
        tips.append(
            MesonSuggestion(
                id="tip-channel-routing",
                nodeType="decision",
                label="Route by channel outcome",
                reason="Branch on delivered / needs-reply / failed so follow-ups stay intentional.",
                confidence=0.73,
                confidenceIsEstimate=True,
                confidenceSource="canvas-tip",
            )
        )
    if "connector" in types and len(nodes) >= 2:
        tips.append(
            MesonSuggestion(
                id="tip-name-data-labels",
                nodeType="task",
                label="Label step outputs",
                reason="Name connector outputs (e.g. $contacts) so agents can reference them reliably.",
                confidence=0.7,
                confidenceIsEstimate=True,
                confidenceSource="canvas-tip",
            )
        )
    if last_name:
        tips.append(
            MesonSuggestion(
                id=f"tip-after-{last_name[:32].lower().replace(' ', '-')}",
                nodeType="task",
                label=f"Document “{last_name[:40]}”",
                reason=f"Add a short instruction on {last_name} so the next run knows the expected inputs/outputs.",
                confidence=0.68,
                confidenceIsEstimate=True,
                confidenceSource="canvas-tip",
            )
        )
    if "hubspot" in names or "hubspot" in vendors:
        tips.append(
            MesonSuggestion(
                id="tip-hubspot-idempotency",
                nodeType="task",
                label="Guard HubSpot duplicates",
                reason="Prefer upsert / email match before create so CRM sync stays idempotent.",
                confidence=0.71,
                confidenceIsEstimate=True,
                confidenceSource="canvas-tip",
            )
        )
    return tips


def _workflow_tip_and_insight_pools(
    *,
    workflow_id: str,
    workflow_name: str,
    nodes: list[dict[str, Any]],
    base_insights: list[MesonInsight],
) -> tuple[list[MesonInsight], list[MesonInsight]]:
    blob = " ".join(
        f"{n.get('type') or ''} {n.get('name') or ''} {n.get('vendor') or ''}".lower()
        for n in nodes
    )
    tips: list[MesonInsight] = [
        MesonInsight(
            id="tip-preview-before-publish",
            title="Preview before publish",
            summary=f"Run a dry-run of {workflow_name} to catch missing actions or unbound agents early.",
            category="tip",
        ),
        MesonInsight(
            id="tip-name-edges",
            title="Keep edges intentional",
            summary="Every step should have a clear next hop — orphan nodes never execute.",
            category="tip",
        ),
        MesonInsight(
            id="tip-connector-health",
            title="Check connector health first",
            summary="Auth expiry is the #1 cause of “sudden” workflow failures — reconnect before re-running.",
            category="tip",
        ),
    ]
    insights: list[MesonInsight] = []
    for item in base_insights:
        cat = (item.category or "").lower()
        if cat == "tip":
            tips.append(item)
            continue
        insights.append(
            item.model_copy(
                update={"category": item.category or "insight"},
            )
        )

    if "apollo" in blob and "clay" in blob:
        tips.extend(
            [
                MesonInsight(
                    id="tip-enrichment-batch-size",
                    title="Start with a small Clay batch",
                    summary="Push a handful of Apollo contacts first — confirm enrichment fields before full list sync.",
                    category="tip",
                ),
                MesonInsight(
                    id="tip-enrichment-list-vars",
                    title="Lock list install variables",
                    summary='Set APOLLO_LIST_NAME and HUBSPOT_LIST_ID so agent steps do not guess list membership.',
                    category="tip",
                ),
            ]
        )
        insights.append(
            MesonInsight(
                id="insight-enrichment-path",
                title="Enrichment path readiness",
                summary=(
                    f"{workflow_name}: Apollo list → Clay enrich → HubSpot CRM → static list. "
                    "Bind Lead Enrichment Coordinator on both agent steps."
                ),
                category="insight",
            )
        )
    if "agent" in blob:
        tips.append(
            MesonInsight(
                id="tip-agent-task-specificity",
                title="Make agent tasks concrete",
                summary="Name tools, list ids, and output variables in the task — vague prompts cause tool thrash.",
                category="tip",
            )
        )
    if len(nodes) >= 5:
        insights.append(
            MesonInsight(
                id="insight-multi-step-observability",
                title="Watch mid-path failures",
                summary=(
                    f"{workflow_name} has {len(nodes)} steps — inspect the first failed node_id in run history "
                    "before rewiring the whole graph."
                ),
                category="insight",
            )
        )
    # Deduplicate by id while preserving order.
    def _dedupe(items: list[MesonInsight]) -> list[MesonInsight]:
        seen: set[str] = set()
        out: list[MesonInsight] = []
        for item in items:
            if item.id in seen:
                continue
            seen.add(item.id)
            out.append(item)
        return out

    return _dedupe(tips), _dedupe(insights)


_meson_service: MesonService | None = None


def get_meson_service() -> MesonService:
    global _meson_service
    if _meson_service is None:
        _meson_service = MesonService()
    return _meson_service
