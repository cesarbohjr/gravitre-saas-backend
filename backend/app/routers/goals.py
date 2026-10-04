from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
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
) -> dict[str, Any]:
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
    inserted = (
        client.table("goal_plans")
        .insert(
            {
                "org_id": org_id,
                "goal_id": goal_id,
                "proposed_steps": proposed_steps,
                "required_connectors": generated.required_connectors or [],
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
            "requiredConnectors": generated.required_connectors,
            "requiredAgents": [],
            "approvalGates": approval_gates,
            "estimatedImpact": estimated_impact,
        },
        "proposedSteps": proposed_steps,
        "requiredConnectors": generated.required_connectors,
        "requiredAgents": [],
        "approvalGates": approval_gates,
        "estimatedImpact": estimated_impact,
    }
