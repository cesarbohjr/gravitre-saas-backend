from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.services.confidence_honesty import CONFIDENCE_SOURCE_HEURISTIC, label_confidence
from app.services.goal_service import get_goal_service

router = APIRouter(prefix="/api/goals", tags=["goals"])


class GeneratePlanRequest(BaseModel):
    objective: str | None = None
    context: str | None = None
    constraints: list[str] = Field(default_factory=list)


@router.post("/{goal_id}/generate-plan")
async def generate_plan(
    goal_id: str,
    body: GeneratePlanRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment_name: Annotated[str, Depends(get_environment_context)] = "production",
) -> dict[str, Any]:
    """Plan a goal with the same objective planner chat, voice and Plays use.

    A measurable goal ("150 qualified leads per month") gets the objective
    plan: Plays as steps, capability-resolved connectors, approvals and an
    honest feasibility estimate. Only a goal that is not measurable falls back
    to drafting a workflow resource for it, which is a resource generator, not
    a second planner.
    """
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    existing = (
        client.table("goals")
        .select("id")
        .eq("id", goal_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    goal_text = (body.objective or "").strip() or "Define measurable goal outcome"
    objective_plan = _goal_plan_from_objective(
        client, org_id, goal_text, environment_name=environment_name, settings=settings, body=body
    )
    if objective_plan is not None:
        return _save_goal_plan(client, org_id, goal_id, objective_plan)

    goal_service = get_goal_service()
    generated = await goal_service.generate_workflow(
        goal=goal_text,
        org_context=body.context,
        org_id=org_id,
    )

    proposed_steps = [
        {
            "id": node.id,
            "title": node.name,
            "owner": generated.department,
            "status": "planned",
        }
        for node in generated.nodes
        if node.type not in ("start", "end")
    ]
    if not proposed_steps:
        proposed_steps = [
            {"id": "step-1", "title": generated.name, "owner": generated.department, "status": "planned"},
        ]

    impact_confidence = 0.75 if generated.risk_level == "low" else 0.6
    estimated_impact = {
        **label_confidence(impact_confidence, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True),
        "expectedLift": generated.success_criteria[0] if generated.success_criteria else "TBD",
        "contextSummary": body.context or "Generated via governed goal planner.",
        "constraints": body.constraints,
    }

    approval_gates = [
        {"phase": "pre-launch", "required": generated.requires_approval, "approverRole": "owner"},
    ]
    return _save_goal_plan(
        client,
        org_id,
        goal_id,
        {
            "proposed_steps": proposed_steps,
            "required_connectors": generated.required_connectors or [],
            "approval_gates": approval_gates,
            "estimated_impact": estimated_impact,
        },
    )


def _goal_plan_from_objective(
    client: Any,
    org_id: str,
    goal_text: str,
    *,
    environment_name: str,
    settings: Settings,
    body: GeneratePlanRequest,
) -> dict[str, Any] | None:
    from app.services.objective_capability_composer import looks_like_objective, plan_objective

    if not looks_like_objective(goal_text):
        return None
    try:
        brief = plan_objective(client, org_id, goal_text, environment_name=environment_name, settings=settings)
    except Exception:  # noqa: BLE001 — fall back to the workflow draft rather than failing the request
        return None
    if not isinstance(brief, dict) or not (brief.get("plan") or {}).get("steps"):
        return None
    plan = brief["plan"]
    contract = brief.get("contract") or {}
    feasibility = brief.get("feasibility") or {}
    department = next(
        (str(r.get("department") or "") for r in brief.get("resources") or [] if r.get("movesPrimary")), ""
    )
    proposed_steps = [
        {
            "id": str(step.get("playKey") or f"step-{idx + 1}"),
            "title": str(step.get("name") or step.get("playKey") or "Step"),
            "owner": department or None,
            "status": "planned" if step.get("status") == "ready" else str(step.get("status") or "planned"),
            "why": step.get("why"),
        }
        for idx, step in enumerate(plan["steps"])
    ]
    connectors: list[str] = []
    for row in (plan.get("capabilityLedger") or {}).values():
        vendor = str((row or {}).get("selected") or "")
        if vendor and vendor != "gravitre" and vendor not in connectors:
            connectors.append(vendor)
    return {
        "proposed_steps": proposed_steps,
        "required_connectors": connectors,
        "approval_gates": [
            {"phase": "pre-launch", "required": bool(plan.get("requiresApproval", True)), "approverRole": "owner"}
        ],
        "estimated_impact": {
            # A target is not a forecast: no confidence number is invented here.
            "verdict": feasibility.get("verdict"),
            "targetIsNotAPromise": True,
            "expectedLift": None,
            "contextSummary": brief.get("summary") or body.context or "Planned by the objective planner.",
            "constraints": body.constraints,
            "objectiveContract": {
                "metricKey": contract.get("metricKey"),
                "target": contract.get("target"),
                "period": contract.get("period"),
            },
        },
    }


def _save_goal_plan(client: Any, org_id: str, goal_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    proposed_steps = plan["proposed_steps"]
    required_connectors = plan["required_connectors"]
    approval_gates = plan["approval_gates"]
    estimated_impact = plan["estimated_impact"]
    inserted = (
        client.table("goal_plans")
        .insert(
            {
                "org_id": org_id,
                "goal_id": goal_id,
                "proposed_steps": proposed_steps,
                "required_connectors": required_connectors,
                "required_agents": [],
                "approval_gates": approval_gates,
                "estimated_impact": estimated_impact,
            }
        )
        .execute()
    )
    if not inserted.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The proposal was generated but could not be saved.",
        )
    plan_id = str(inserted.data[0]["id"])

    return {
        "planId": plan_id,
        "goalPlan": {
            "id": plan_id,
            "goalId": goal_id,
            "proposedSteps": proposed_steps,
            "requiredConnectors": required_connectors,
            "requiredAgents": [],
            "approvalGates": approval_gates,
            "estimatedImpact": estimated_impact,
        },
        "proposedSteps": proposed_steps,
        "requiredConnectors": required_connectors,
        "requiredAgents": [],
        "approvalGates": approval_gates,
        "estimatedImpact": estimated_impact,
    }


# --------------------------------------------------------------------------- objectives
# An objective is a goal whose success_metrics hold an objective contract on a
# canonical, source-verified metric. Planning, progress and replanning run on
# the Outcome Ownership composer; execution runs through the canonical Play runtime.


class ObjectiveRequest(BaseModel):
    statement: str = Field(..., min_length=3, max_length=800)
    metric_key: str | None = Field(default=None, alias="metricKey", max_length=120)
    target: float | None = None
    period: str | None = Field(default=None, pattern="^(week|month|quarter|year)$")
    definition_confirmed: bool = Field(default=False, alias="definitionConfirmed")

    model_config = {"populate_by_name": True}


def _objective_org(org_id: str | None) -> str:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return org_id


def _objective_brief(body: ObjectiveRequest, client: Any, org_id: str, environment_name: str, settings: Settings) -> dict[str, Any]:
    from app.services.objective_capability_composer import plan_objective

    brief = plan_objective(
        client,
        org_id,
        body.statement,
        metric_key=body.metric_key,
        target=body.target,
        period=body.period,
        environment_name=environment_name,
        settings=settings,
    )
    if body.definition_confirmed and isinstance(brief.get("contract"), dict):
        brief["contract"]["definitionConfirmed"] = True
    return brief


@router.post("/objectives/plan")
async def preview_objective_plan(
    body: ObjectiveRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    from app.services.objective_capability_composer import public_brief

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return public_brief(_objective_brief(body, client, _objective_org(org_id), environment_name, settings))


@router.post("/objectives")
async def create_objective(
    body: ObjectiveRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    from app.services.objective_capability_composer import save_objective

    org = _objective_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    brief = _objective_brief(body, client, org, environment_name, settings)
    if not brief.get("plan"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=brief.get("summary") or "Objective needs a metric")
    return save_objective(client, org, brief, status="active" if body.definition_confirmed else "draft")


@router.get("/objectives/{objective_id}/progress")
async def get_objective_progress(
    objective_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    from app.services.objective_capability_composer import objective_progress

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    progress = objective_progress(client, _objective_org(org_id), objective_id)
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")
    return progress


@router.post("/objectives/{objective_id}/replan")
async def replan_objective_route(
    objective_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    from app.services.objective_capability_composer import replan_objective

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = replan_objective(
        client, _objective_org(org_id), objective_id, environment_name=environment_name, settings=settings, reason="requested", force=True
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")
    return result


@router.post("/objectives/{objective_id}/execute")
async def execute_objective(
    objective_id: str,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Start every runnable plan step through the canonical Play runtime (approval gates apply)."""
    from app.routers.plays import RunPlayRequest, run_play
    from app.services.objective_capability_composer import execution_requests, load_objective, org_context

    org = _objective_org(org_id)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    goal = load_objective(client, org, objective_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")
    steps = (goal.get("plan") or {}).get("proposed_steps") or []
    installs = org_context(client, org, environment_name=environment_name)["playInstallations"]
    requests = execution_requests(steps, installs, objective_id)
    started = []
    for request in requests:
        if request["state"] != "runnable":
            continue
        try:
            result = await run_play(
                request["playKey"],
                RunPlayRequest(
                    installationId=str(request["installationId"]),
                    objectiveId=objective_id,
                    capabilityVendors=request["capabilityVendors"],
                ),
                member=(user, org, "member"),
                environment_name=environment_name,
                settings=settings,
            )
            request["state"] = "started"
            request["playRunId"] = result.get("playRunId")
            request["runStatus"] = result.get("status")
            started.append(request["playKey"])
        except HTTPException as exc:
            request["state"] = "not_started"
            request["reason"] = exc.detail
    client.table("goals").update({"status": "active"}).eq("id", objective_id).eq("org_id", org).execute()
    return {"objectiveId": objective_id, "started": started, "steps": requests}
