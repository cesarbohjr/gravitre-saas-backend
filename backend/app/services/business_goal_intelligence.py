"""Cross-department business goal interpretation, grounded in the existing GoalService.

This is the canonical semantic intake for goal planning, not an autonomous
executor or a keyword router. It accepts any business goal/question and
returns typed intent, connected evidence coverage and executable readiness.
The existing model router supplies business-domain interpretation; all
connector availability and effects still require tenant-scoped verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.services.goal_service import GoalAnalysis, GoalService


@dataclass(frozen=True)
class BusinessGoal:
    text: str
    intent: str
    department: str
    objective_family: str | None
    entities: tuple[str, ...]
    success_metrics: tuple[str, ...]
    risk_factors: tuple[str, ...]
    required_systems: tuple[str, ...]
    connected_systems: tuple[str, ...]
    missing_systems: tuple[str, ...]
    understanding_status: str
    execution_status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text, "intent": self.intent,
            "department": self.department,
            "objective_family": self.objective_family,
            "entities": list(self.entities),
            "success_metrics": list(self.success_metrics),
            "risk_factors": list(self.risk_factors),
            "required_systems": list(self.required_systems),
            "connected_systems": list(self.connected_systems),
            "missing_systems": list(self.missing_systems),
            "understanding_status": self.understanding_status,
            "execution_status": self.execution_status,
        }


def interpret_business_analysis(
    *,
    goal: str,
    analysis: GoalAnalysis,
    tenant_connectors: Iterable[str],
) -> BusinessGoal:
    """Normalize model analysis without trusting claimed connector availability.

    A model can name required systems but cannot grant credentials, create a
    registered action, or declare the request executable. Those gates are
    separate. The department is inferred semantically, never by keyword list.
    """
    if not str(goal or "").strip():
        raise ValueError("business_goal_required")
    connected = {str(x).strip().lower() for x in tenant_connectors if str(x).strip()}
    required = tuple(dict.fromkeys(str(x).strip().lower() for x in analysis.required_systems if str(x).strip()))
    present = tuple(x for x in required if x in connected)
    missing = tuple(x for x in required if x not in connected)
    return BusinessGoal(
        text=goal.strip(),
        intent=analysis.intent.strip() or goal.strip(),
        department=analysis.department.strip().lower() or "cross_functional",
        objective_family=analysis.objective_family,
        entities=tuple(analysis.key_entities),
        success_metrics=tuple(analysis.success_metrics),
        risk_factors=tuple(analysis.risk_factors),
        required_systems=required,
        connected_systems=present,
        missing_systems=missing,
        understanding_status="ANALYZED_UNVERIFIED",
        execution_status="NOT_RUN",
    )


async def analyze_business_goal_for_org(
    *,
    goal: str,
    org_id: str,
    settings: Any,
    department_hint: str | None = None,
    success_metric: str | None = None,
    org_context: str | None = None,
    goal_service: GoalService | None = None,
) -> BusinessGoal:
    """Use existing model-routed intent analysis and real tenant connections.

    The caller is responsible for verifying authorization to org_id.
    No workflow execution, provider mutation or revenue claim occurs here.
    """
    if not org_id or not org_id.strip():
        raise ValueError("authenticated_org_required")
    if not goal or not goal.strip():
        raise ValueError("business_goal_required")
    from app.services.agent_selector import AgentSelector

    connected = await AgentSelector(settings=settings)._get_connected(org_id)
    service = goal_service or GoalService()
    analysis = await service._analyze_goal(
        goal, department_hint, sorted(connected),
        success_metric, org_context, org_id,
    )
    return interpret_business_analysis(
        goal=goal, analysis=analysis, tenant_connectors=connected,
    )
