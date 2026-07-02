"""Council → workflow branch integration (STA-48)."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from app.config import Settings
from app.services.council_service import AgentCouncilService, DecisionMethod, get_council_service
from app.services.handoff_service import get_agent
from app.workflows.constants import SCHEMA_VERSION
from app.workflows.repository import (
    create_workflow_version,
    get_active_workflow_version,
    get_next_workflow_version_number,
    set_active_workflow_version,
)

logger = logging.getLogger(__name__)

COUNCIL_WORKFLOW_SEED_LABEL = "workflow:uncertain-lead-council"
COUNCIL_WORKFLOW_NAME = "Uncertain lead → Council → Enroll or nurture"
DEFAULT_CONFIDENCE_THRESHOLD = 0.75


def _org_namespace(org_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(org_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{org_id}")


def council_branch_workflow_id(org_id: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), f"gravitre-seed:{COUNCIL_WORKFLOW_SEED_LABEL}"))


def sales_agent_id(org_id: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), "gravitre-seed:agent:sales"))


def marketing_agent_id(org_id: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), "gravitre-seed:agent:marketing"))


def resolve_active_branch(step_outputs: dict[str, Any]) -> str | None:
    """Return the branch selected by the most recent council step output."""
    branch: str | None = None
    for output in step_outputs.values():
        if isinstance(output, dict) and output.get("branch"):
            branch = str(output["branch"])
    return branch


def should_skip_for_branch(config: dict[str, Any], active_branch: str | None) -> bool:
    when_branch = config.get("when_branch")
    if not when_branch:
        return False
    if active_branch is None:
        return True
    return str(when_branch) != str(active_branch)


def map_recommendation_to_branch(
    recommendation: str,
    output_paths: dict[str, Any] | None,
    options: list[str] | None = None,
) -> str:
    paths = output_paths or {}
    if recommendation in paths:
        return str(paths[recommendation])
    if recommendation in paths.values():
        return str(recommendation)
    opts = options or []
    if recommendation in opts:
        return str(recommendation)
    for key, value in paths.items():
        if str(key).lower() == str(recommendation).lower():
            return str(value)
        if str(value).lower() == str(recommendation).lower():
            return str(value)
    return str(recommendation or (opts[0] if opts else "default"))


def should_escalate_to_council(
    source_output: dict[str, Any] | None,
    *,
    threshold: float,
) -> bool:
    if not source_output:
        return True
    confidence = source_output.get("confidence")
    if confidence is None and isinstance(source_output.get("source_output"), dict):
        confidence = source_output["source_output"].get("confidence")
    if confidence is None:
        return True
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return True
    if value > 1.0:
        value = value / 100.0
    return value < threshold


def load_council_agents(client: Any, org_id: str, agent_ids: list[str]) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for agent_id in agent_ids:
        row = get_agent(client, org_id, str(agent_id))
        if not row:
            continue
        agents.append(
            {
                "id": str(row["id"]),
                "name": row.get("name"),
                "role": (row.get("role") or row.get("purpose") or "analyst").split()[0].lower(),
                "weight": float((row.get("config") or {}).get("council_weight") or 1.0),
            }
        )
    return agents


def default_council_agents(org_id: str) -> list[dict[str, Any]]:
    return [
        {"id": sales_agent_id(org_id), "name": "Sales Agent", "role": "advocate", "weight": 1.0},
        {"id": marketing_agent_id(org_id), "name": "Marketing Agent", "role": "strategist", "weight": 1.0},
        {
            "name": "Compliance Reviewer",
            "role": "compliance",
            "weight": 1.2,
            "is_chair": False,
        },
    ]


def _resolve_objective(config: dict[str, Any], parameters: dict[str, Any], step_outputs: dict[str, Any]) -> str:
    objective = config.get("objective") or (config.get("metadata") or {}).get("objective")
    if isinstance(objective, str) and objective.startswith("$"):
        return str(parameters.get(objective[1:], "") or "Evaluate workflow decision")
    if objective:
        return str(objective)
    return str(parameters.get("objective") or "Evaluate workflow decision")


def _source_step_output(config: dict[str, Any], step_outputs: dict[str, Any]) -> dict[str, Any] | None:
    source_step_id = config.get("source_step_id") or (config.get("metadata") or {}).get("source_step_id")
    if not source_step_id:
        return None
    output = step_outputs.get(str(source_step_id))
    return output if isinstance(output, dict) else None


async def execute_council_step(
    settings: Settings,
    *,
    org_id: str,
    user_id: str,
    run_id: str,
    workflow_id: str,
    step_id: str,
    config: dict[str, Any],
    parameters: dict[str, Any],
    step_outputs: dict[str, Any],
    client: Any,
    council_service: AgentCouncilService | None = None,
) -> dict[str, Any]:
    """Run council when confidence is low; return selected workflow branch."""
    council = council_service or get_council_service()
    metadata = config.get("metadata") if isinstance(config.get("metadata"), dict) else {}
    council_cfg = config.get("councilConfig") if isinstance(config.get("councilConfig"), dict) else {}
    merged = {**metadata, **council_cfg, **config}

    options = list(merged.get("options") or ["enroll", "nurture"])
    output_paths = merged.get("output_paths") or merged.get("outputPaths") or {}
    threshold = float(merged.get("confidence_threshold") or merged.get("confidenceThreshold") or DEFAULT_CONFIDENCE_THRESHOLD)
    default_branch = str(merged.get("default_branch") or merged.get("defaultBranch") or options[0])

    source_output = _source_step_output(merged, step_outputs)
    escalated = should_escalate_to_council(source_output, threshold=threshold)

    if not escalated:
        branch = default_branch
        if source_output:
            rec = source_output.get("summary") or (source_output.get("source_output") or {}).get("summary")
            if rec and str(rec).lower() in {str(o).lower() for o in options}:
                branch = map_recommendation_to_branch(str(rec), output_paths, options)
        return {
            "branch": branch,
            "escalated": False,
            "final_recommendation": branch,
            "final_confidence": float(
                source_output.get("confidence")
                or (source_output.get("source_output") or {}).get("confidence")
                or 1.0
            )
            if source_output
            else 1.0,
            "council_session_id": None,
        }

    agent_ids = merged.get("agent_ids") or merged.get("agentIds") or []
    agents = load_council_agents(client, org_id, [str(a) for a in agent_ids]) if agent_ids else []
    if not agents:
        agents = default_council_agents(org_id)

    method_raw = str(merged.get("decision_method") or merged.get("decisionMethod") or "majority_vote")
    try:
        decision_method = DecisionMethod(method_raw)
    except ValueError:
        decision_method = DecisionMethod.MAJORITY_VOTE

    evidence = {
        "parameters": parameters,
        "prior_steps": step_outputs,
        "source_step": source_output,
    }
    objective = _resolve_objective(merged, parameters, step_outputs)

    session = await council.start_council(
        org_id=org_id,
        workflow_id=workflow_id or str(parameters.get("workflow_id") or ""),
        run_id=run_id,
        objective=objective,
        options=options,
        agents=agents,
        evidence=evidence,
        decision_method=decision_method,
        max_rounds=int(merged.get("max_rounds") or merged.get("maxRounds") or 2),
    )
    branch = map_recommendation_to_branch(session.final_recommendation, output_paths, options)
    return {
        "branch": branch,
        "escalated": True,
        "final_recommendation": session.final_recommendation,
        "final_confidence": session.final_confidence,
        "council_session_id": session.id,
        "decision_method": session.decision_method.value,
        "dissenting_opinions": session.dissenting_opinions,
    }


def build_uncertain_lead_council_workflow_definition(*, org_id: str) -> dict[str, Any]:
    """Demo: Sales qualifies lead → council if uncertain → enroll or nurture branch."""
    sales_id = sales_agent_id(org_id)
    marketing_id = marketing_agent_id(org_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "steps": [
            {
                "id": "sales_qualify",
                "name": "Sales qualifies inbound lead",
                "type": "agent",
                "metadata": {
                    "agent_id": sales_id,
                    "task": (
                        "Qualify the inbound lead and score fit. Return confidence 0-100. "
                        "Recommend enroll for high-intent leads or nurture for early-stage leads."
                    ),
                },
            },
            {
                "id": "council_escalation",
                "name": "Council reviews uncertain leads",
                "type": "council",
                "config": {
                    "source_step_id": "sales_qualify",
                    "confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD,
                    "objective": "Should this lead be enrolled in an active sequence or nurtured?",
                    "options": ["enroll", "nurture"],
                    "output_paths": {"enroll": "enroll", "nurture": "nurture"},
                    "decision_method": "majority_vote",
                    "agent_ids": [sales_id, marketing_id],
                },
            },
            {
                "id": "marketing_enroll",
                "name": "Marketing enrolls high-intent lead",
                "type": "agent",
                "config": {"when_branch": "enroll"},
                "metadata": {
                    "agent_id": marketing_id,
                    "task": "Enroll the lead in the primary outbound sequence.",
                },
            },
            {
                "id": "marketing_nurture",
                "name": "Marketing nurtures early-stage lead",
                "type": "agent",
                "config": {"when_branch": "nurture"},
                "metadata": {
                    "agent_id": marketing_id,
                    "task": "Add the lead to a long-term nurture track with educational content.",
                },
            },
        ],
    }


def ensure_uncertain_lead_council_workflow(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> str:
    workflow_id = council_branch_workflow_id(org_id)
    definition = build_uncertain_lead_council_workflow_definition(org_id=org_id)
    workflow_config = {"demo": True, "council_branch": True}

    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": COUNCIL_WORKFLOW_NAME,
            "description": "Low-confidence sales qualification escalates to council; branch enroll vs nurture.",
            "status": "active",
            "schema_version": SCHEMA_VERSION,
            "definition": definition,
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()

    client.table("workflows").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": COUNCIL_WORKFLOW_NAME,
            "description": "Council branches marketing actions when sales confidence is below threshold.",
            "status": "active",
            "environment": environment_name,
            "nodes": [
                {"id": "sales", "type": "agent", "name": "Sales qualify"},
                {"id": "council", "type": "council", "name": "Council"},
                {"id": "enroll", "type": "agent", "name": "Enroll"},
                {"id": "nurture", "type": "agent", "name": "Nurture"},
            ],
            "edges": [
                {"from": "sales", "to": "council"},
                {"from": "council", "to": "enroll"},
                {"from": "council", "to": "nurture"},
            ],
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()

    if not get_active_workflow_version(client, org_id, workflow_id, environment_name):
        version_number = get_next_workflow_version_number(client, org_id, workflow_id, environment_name)
        version_row = create_workflow_version(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            environment_name=environment_name,
            version=version_number,
            definition=definition,
            schema_version=SCHEMA_VERSION,
            created_by=None,
        )
        set_active_workflow_version(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            environment_name=environment_name,
            version_id=str(version_row["id"]),
            updated_by=None,
        )

    org_row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings_row = (org_row.data or [{}])[0].get("settings") or {}
    if isinstance(settings_row, dict):
        onboarding = settings_row.get("onboarding") if isinstance(settings_row.get("onboarding"), dict) else {}
        onboarding = dict(onboarding)
        onboarding["demo_council_workflow_id"] = workflow_id
        settings_row["onboarding"] = onboarding
        client.table("organizations").update({"settings": settings_row}).eq("id", org_id).execute()

    logger.info("council_workflow_ensured org_id=%s workflow_id=%s", org_id, workflow_id)
    return workflow_id


def on_council_workflow_org_ready(client: Any, org_id: str, settings: Settings) -> None:
    _ = settings
    try:
        ensure_uncertain_lead_council_workflow(client, org_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("council_workflow_setup_failed org_id=%s error=%s", org_id, exc)
