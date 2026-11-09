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
    assert result.connected_systems == ["hubspot"]
    assert result.missing_systems == ["zendesk"]
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


@pytest.mark.asyncio
async def test_goal_service_discovers_missing_evidence_without_granting_tools():
    from app.services.goal_service import GoalService
    class Model:
        prompt = ""
        async def complete(self, **kw):
            self.prompt = kw["prompt"]
            return SimpleNamespace(parsed={
                "intent": "reduce churn", "department": "customer_success",
                "objective_family": "reduce_churn",
                "key_entities": ["accounts"],
                "required_systems": ["hubspot", "zendesk"],
                "complexity": "moderate", "risk_factors": [],
                "success_metrics": ["retention_rate"],
            })
    model = Model()
    service = GoalService(model_router=model)
    analysis = await service._analyze_goal(
        "Our customers keep leaving", None, ["hubspot"],
        None, "support queues are long", "tenant-one",
    )
    normalized = service.normalize_analysis(analysis, {"hubspot"})
    assert "even if not connected" in model.prompt
    assert "User-supplied contextual notes (unverified)" in model.prompt
    assert normalized.connected_systems == ["hubspot"]
    assert normalized.missing_systems == ["zendesk"]
    assert normalized.execution_status == "NOT_RUN"


def test_generated_goal_draft_has_valid_structural_contract():
    service = GoalService(model_router=object())
    analysis = GoalAnalysis(
        intent="Investigate revenue", department="sales",
        key_entities=["deals"], required_systems=["hubspot"],
        complexity="moderate", risk_factors=[], success_metrics=["pipeline"],
    )
    for approval_required in (True, False):
        draft = service._build_definition("Investigate revenue", analysis, approval_required)
        service._validate_definition(draft)


@pytest.mark.parametrize("mutation,error", [
    ("duplicate_node", "unique nonempty IDs"),
    ("duplicate_edge", "unique nonempty IDs"),
    ("cycle", "cycle"),
    ("orphan", "disconnected or dead-end"),
    ("dead_end", "disconnected or dead-end"),
    ("wrong_start_type", "start/end node types"),
    ("missing_approval", "requires an approval node"),
    ("backward_start", "start/end direction"),
])
def test_goal_draft_rejects_malformed_or_unsafe_graphs(mutation, error):
    from app.services.goal_service import WorkflowEdge, WorkflowNode

    service = GoalService(model_router=object())
    analysis = GoalAnalysis(
        intent="Investigate revenue", department="sales",
        key_entities=["deals"], required_systems=["hubspot"],
        complexity="moderate", risk_factors=[], success_metrics=["pipeline"],
    )
    draft = service._build_definition("Investigate revenue", analysis, True)
    if mutation == "duplicate_node":
        draft.nodes.append(draft.nodes[1].model_copy())
    elif mutation == "duplicate_edge":
        draft.edges.append(draft.edges[0].model_copy())
    elif mutation == "cycle":
        draft.edges.append(WorkflowEdge(id="cycle-edge", source="decision", target="process"))
    elif mutation == "orphan":
        draft.nodes.append(WorkflowNode(id="orphan", type="action", name="Orphan"))
    elif mutation == "dead_end":
        draft.nodes.append(WorkflowNode(id="dead", type="action", name="Dead"))
        draft.edges.append(WorkflowEdge(id="to-dead", source="start", target="dead"))
    elif mutation == "wrong_start_type":
        draft.nodes[0].type = "action"
    elif mutation == "missing_approval":
        draft.nodes = [node for node in draft.nodes if node.id != "approval"]
        draft.edges = [edge for edge in draft.edges if edge.source != "approval" and edge.target != "approval"]
        draft.edges.append(WorkflowEdge(id="skip-approval", source="decision", target="end"))
    elif mutation == "backward_start":
        draft.edges.append(WorkflowEdge(id="backward", source="decision", target="start"))
    with pytest.raises(ValueError, match=error):
        service._validate_definition(draft)


def test_tenant_metric_evidence_preserves_lineage_and_no_outcome_claim():
    from datetime import datetime, timedelta, timezone
    from app.services.goal_service import BusinessMetricEvidence

    now = datetime(2026, 11, 8, tzinfo=timezone.utc)
    analysis = GoalAnalysis(
        intent="Improve pipeline", department="sales",
        key_entities=["deals"], required_systems=["hubspot", "salesforce"],
        complexity="moderate", risk_factors=[], success_metrics=["pipeline_value"],
    )
    current = BusinessMetricEvidence(
        org_id="org-A", system="hubspot", source_record_id="deal-1",
        metric_key="pipeline_value", unit="USD", value=2500,
        observed_at=now - timedelta(hours=1),
    )
    stale = current.model_copy(update={"source_record_id": "deal-2", "observed_at": now - timedelta(days=9)})
    future = current.model_copy(update={"source_record_id": "deal-3", "observed_at": now + timedelta(minutes=1)})
    unverified = current.model_copy(update={"system": "unknown"})
    no_lineage = current.model_copy(update={"source_record_id": ""})
    naive = current.model_copy(update={"observed_at": datetime(2026, 11, 8)})
    result = GoalService.assess_evidence_for_org(
        org_id="org-A", analysis=analysis, connected_systems={"hubspot"},
        observations=[current, stale, future, unverified, no_lineage, naive], as_of=now,
    )
    assert result.status == "EVIDENCE_AVAILABLE_UNINTERPRETED"
    assert result.usable == [current]
    assert result.missing_systems == ["salesforce"]
    assert result.business_outcome == "NOT_MEASURED"
    assert {item["reason"] for item in result.excluded} == {
        "stale_observation", "future_observation", "unverified_or_unrequired_source",
        "missing_metric_provenance", "missing_observation_timezone",
    }


def test_metric_evidence_fails_closed_on_cross_tenant_records():
    from datetime import datetime, timezone
    from app.services.goal_service import BusinessMetricEvidence

    now = datetime(2026, 11, 8, tzinfo=timezone.utc)
    analysis = GoalAnalysis(
        intent="Audit spend", department="finance", key_entities=["invoices"],
        required_systems=["quickbooks"], complexity="simple",
        risk_factors=[], success_metrics=["spend"],
    )
    record = BusinessMetricEvidence(
        org_id="org-B", system="quickbooks", source_record_id="invoice-secret",
        metric_key="spend", unit="CAD", value=100, observed_at=now,
    )
    with pytest.raises(ValueError, match="cross_tenant_metric_evidence"):
        GoalService.assess_evidence_for_org(
            org_id="org-A", analysis=analysis, connected_systems={"quickbooks"},
            observations=[record], as_of=now,
        )


def test_metric_evidence_missing_connection_never_claims_diagnosis():
    from datetime import datetime, timezone

    analysis = GoalAnalysis(
        intent="Reduce churn", department="support", key_entities=["accounts"],
        required_systems=["zendesk"], complexity="moderate",
        risk_factors=[], success_metrics=["churn"],
    )
    result = GoalService.assess_evidence_for_org(
        org_id="org-A", analysis=analysis, connected_systems=set(),
        observations=[], as_of=datetime(2026, 11, 8, tzinfo=timezone.utc),
    )
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.missing_systems == ["zendesk"]
    assert result.usable == []
    assert result.business_outcome == "NOT_MEASURED"
