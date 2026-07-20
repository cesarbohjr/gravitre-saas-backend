from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
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
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")

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

    return {
        "goalPlan": {
            "goalId": goal_id,
            "proposedSteps": proposed_steps,
            "requiredConnectors": generated.required_connectors,
            "requiredAgents": [],
            "approvalGates": [
                {"phase": "pre-launch", "required": generated.requires_approval, "approverRole": "owner"},
            ],
            "estimatedImpact": estimated_impact,
        },
        "proposedSteps": proposed_steps,
        "requiredConnectors": generated.required_connectors,
        "requiredAgents": [],
        "approvalGates": [
            {"phase": "pre-launch", "required": generated.requires_approval, "approverRole": "owner"},
        ],
        "estimatedImpact": estimated_impact,
    }
