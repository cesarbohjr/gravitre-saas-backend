"""Cross-department semantic intent intake: no sales keyword routing."""
from __future__ import annotations

from types import SimpleNamespace
import pytest

from app.services.goal_service import GoalAnalysis, GoalService


@pytest.mark.parametrize("department,family,prompt,systems", [
    ("sales", "grow_revenue", "Our deals keep slipping; get bookings growing", ["hubspot"]),
    ("finance", "reduce_cost", "Why is our cash burn accelerating?", ["quickbooks"]),
    ("support", "improve_support", "Our customers are waiting too long", ["zendesk"]),
    ("operations", "improve_operations", "How do we reduce fulfillment delays?", ["netsuite"]),
    ("engineering", "improve_security", "Lower our production incident rate", ["github"]),
    ("marketing", "grow_revenue", "Our campaigns bring traffic but no customers", ["google_analytics"]),
])
def test_any_business_goal_preserves_semantic_context_without_keyword_gate(
    department, family, prompt, systems,
):
    analysis = GoalAnalysis(
        intent=prompt, department=department, objective_family=family,
        key_entities=["organization"], required_systems=systems,
        complexity="moderate", risk_factors=["data gaps"],
        success_metrics=["baseline and change"],
    )
    result = GoalService.normalize_analysis(analysis, {"hubspot"})
    assert result.department == department
    assert result.objective_family == family
    assert result.execution_status == "NOT_RUN"
    assert result.understanding_status == "ANALYZED_UNVERIFIED"
    assert set(result.connected_systems).isdisjoint(result.missing_systems)


@pytest.mark.asyncio
async def test_org_goal_analysis_uses_existing_model_semantics_and_tenant_connections(monkeypatch):
    from app.services import agent_selector

    class Selector:
        def __init__(self, settings):
            pass
        async def _get_connected(self, org):
            assert org == "tenant-one"
            return {"hubspot", "platform"}
    monkeypatch.setattr(agent_selector, "AgentSelector", Selector)

    class ModelGoalService:
        async def _analyze_goal(self, goal, department, connectors, metric, context, org):
            assert org == "tenant-one"
            assert "hubspot" in connectors
            return GoalAnalysis(
                intent="improve customer retention", department="customer_success",
                objective_family="reduce_churn", key_entities=["renewals"],
                required_systems=["hubspot", "zendesk"], complexity="complex",
                risk_factors=["unobserved support history"],
                success_metrics=["retention"],
            )

    service = GoalService(model_router=object())
    service._analyze_goal = ModelGoalService()._analyze_goal
    result = await service.analyze_for_org(
        goal="Our customers keep leaving. Why?",
        org_id="tenant-one", settings=object(),
    )
    assert result.department == "customer_success"
    assert result.objective_family == "reduce_churn"
    assert result.connected_systems == ("hubspot",)
    assert result.missing_systems == ("zendesk",)
    assert result.execution_status == "NOT_RUN"


@pytest.mark.asyncio
async def test_no_org_refuses_semantic_analysis():
    with pytest.raises(ValueError, match="authenticated_org_required"):
        await GoalService(model_router=object()).analyze_for_org(
            goal="Improve margins", org_id="", settings=object(),
        )


@pytest.mark.asyncio
async def test_model_fallback_never_invents_department_kpi_or_executable_state():
    from types import SimpleNamespace
    from app.services.goal_service import GoalService

    class UnavailableModel:
        async def complete(self, **kwargs):
            raise RuntimeError("LLM unavailable")

    service = GoalService(model_router=UnavailableModel())
    result = await service._analyze_goal(
        "What is going wrong with my business?",
        None, [], None, None, "tenant-one",
    )
    assert result.department == "cross_functional"
    assert result.success_metrics == []
    assert result.objective_family is None
    assert result.understanding_status == "FALLBACK_UNVERIFIED"
    assert result.execution_status == "NOT_RUN"
