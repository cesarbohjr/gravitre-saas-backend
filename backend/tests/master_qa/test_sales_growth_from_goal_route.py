"""Existing from-goal API must persist compiled sales canvas and never auto-run."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.workflows.sales_growth_recipe import (
    GoalCompilationBlocked, compile_sales_growth_goal,
)


def _plan():
    return compile_sales_growth_goal(
        goal="I need to increase sales",
        recognized_objective="increase_sales",
        connected_integrations=["hubspot"],
        action_entries=[SimpleNamespace(
            connector_id="hubspot", action_key="hubspot.contacts.search",
            display_name="Inspect leads", kind="read",
            chat_executable=True, invoke_tool_handler="hubspot.contacts.search",
            implementation_status="executable",
        )],
    )


@pytest.mark.asyncio
async def test_from_goal_persists_real_canvas_but_never_executes(monkeypatch):
    from app.routers import workflows
    from app.workflows import sales_growth_recipe
    from app.services.goal_service import GoalAnalysis

    async def analyze(**kwargs):
        return GoalAnalysis(
            intent="increase sales", department="sales",
            objective_family="grow_revenue", key_entities=["deals"],
            required_systems=["hubspot"], complexity="moderate",
            risk_factors=[], success_metrics=["pipeline"],
        )
    plan = _plan()
    calls = []
    row = None

    class Table:
        def insert(self, payload):
            nonlocal row
            row = payload
            calls.append("persist_draft")
            return self
        def execute(self):
            return SimpleNamespace(data=[{**row, "id": "workflow-test-id"}])

    client = SimpleNamespace(table=lambda name: Table() if name == "workflow_defs" else None)
    monkeypatch.setattr(workflows, "get_supabase_client", lambda settings: client)

    async def compile_for_org(**kwargs):
        assert kwargs["org_id"] == "tenant-1"
        calls.append("tenant_compiler")
        return plan
    monkeypatch.setattr(sales_growth_recipe, "compile_sales_growth_for_org", compile_for_org)
    monkeypatch.setattr(workflows, "mirror_legacy_workflow_row_to_contract",
                        lambda *_args, **_kwargs: calls.append("mirror"))

    def save_builder(_client, **kwargs):
        calls.append("save_actual_builder")
        assert kwargs["org_id"] == "tenant-1"
        assert kwargs["nodes"] == plan.graph["nodes"]
        assert kwargs["edges"] == plan.graph["edges"]
        return kwargs["nodes"], kwargs["edges"], plan.workflow_definition

    monkeypatch.setattr(workflows, "sync_builder_graph", save_builder)
    monkeypatch.setattr(workflows, "_node_out", lambda node: node)
    monkeypatch.setattr(workflows, "_edge_out", lambda edge: edge)
    monkeypatch.setattr(workflows, "write_audit_event",
                        lambda *_args, **_kwargs: calls.append("audit"))

    class ShouldNotGenerate:
        analyze_for_org = staticmethod(analyze)
        async def generate_workflow(self, **kwargs):
            raise AssertionError("legacy model outline must not replace bounded sales plan")

    result = await workflows.create_workflow_from_goal(
        workflows.GoalWorkflowRequest(goal="I need to increase sales"),
        ({"user_id": "operator-1"}, "tenant-1"),
        "synthetic", object(), ShouldNotGenerate(),
    )
    assert result["id"] == "workflow-test-id"
    assert result["status"] == "draft"
    assert result["execution_status"] == "NOT_RUN"
    assert result["business_outcome"] == "NOT_MEASURED"
    assert len(result["canvas"]["nodes"]) == 2
    assert len(result["canvas"]["edges"]) == 1
    assert row["org_id"] == "tenant-1"
    assert row["status"] == "draft"
    assert "execute" not in calls
    assert calls == ["tenant_compiler", "persist_draft", "mirror", "save_actual_builder", "audit"]


@pytest.mark.asyncio
async def test_from_goal_missing_connected_read_fails_before_database_write(monkeypatch):
    from app.routers import workflows
    from app.workflows import sales_growth_recipe
    from app.services.goal_service import GoalAnalysis
    async def analyze(**kwargs):
        return GoalAnalysis(
            intent="increase sales", department="sales",
            objective_family="grow_revenue", key_entities=[],
            required_systems=["hubspot"], complexity="moderate",
            risk_factors=[], success_metrics=[],
        )

    async def blocked(**kwargs):
        raise GoalCompilationBlocked("no_connected_executable_sales_read")
    monkeypatch.setattr(sales_growth_recipe, "compile_sales_growth_for_org", blocked)
    monkeypatch.setattr(workflows, "get_supabase_client",
                        lambda *_: (_ for _ in ()).throw(AssertionError("no DB writes")))
    with pytest.raises(HTTPException) as info:
        await workflows.create_workflow_from_goal(
            workflows.GoalWorkflowRequest(goal="increase sales"),
            ({"user_id": "operator-1"}, "tenant-1"),
            "synthetic", object(),
            SimpleNamespace(analyze_for_org=analyze),
        )
    assert info.value.status_code == 409


@pytest.mark.asyncio
async def test_from_goal_routes_support_objective_to_general_semantic_draft(monkeypatch):
    """Non-sales goals are understood but not misrepresented as executable."""
    from app.routers import workflows
    from app.workflows import sales_growth_recipe
    calls = []

    from app.services.goal_service import GoalAnalysis
    async def analyze(**kwargs):
        calls.append("analyze")
        return GoalAnalysis(
            intent="investigate tickets", department="support",
            objective_family="improve_support", key_entities=["tickets"],
            required_systems=["zendesk"], complexity="moderate",
            risk_factors=[], success_metrics=["ticket_resolution_time"],
        )

    async def forbidden_sales_compiler(**kwargs):
        raise AssertionError("support goals must not be routed to sales compiler")
    monkeypatch.setattr(sales_growth_recipe, "compile_sales_growth_for_org", forbidden_sales_compiler)

    class Query:
        def insert(self, payload):
            calls.append("persist_draft")
            assert payload["status"] == "draft"
            return self
        def execute(self):
            return SimpleNamespace(data=[{"id": "support-draft"}])
    monkeypatch.setattr(workflows, "get_supabase_client", lambda settings:
                        SimpleNamespace(table=lambda name: Query()))
    monkeypatch.setattr(workflows, "mirror_legacy_workflow_row_to_contract",
                        lambda *args, **kwargs: None)
    monkeypatch.setattr(workflows, "write_audit_event",
                        lambda *args, **kwargs: None)

    class Generated:
        name = "Support diagnostic"
        goal = "Why are our support tickets escalating?"
        description = "Support investigation"
        department = "support"
        nodes = []
        edges = []
        def model_dump(self):
            return {"name": self.name, "department": self.department}

    class GoalService:
        analyze_for_org = staticmethod(analyze)
        async def generate_workflow(self, **kwargs):
            calls.append("general_goal_service")
            return Generated()

    result = await workflows.create_workflow_from_goal(
        workflows.GoalWorkflowRequest(goal="Why are our support tickets escalating?"),
        ({"user_id": "operator-1"}, "tenant-1"),
        "synthetic", object(), GoalService(),
    )
    assert result["id"] == "support-draft"
    assert result["business_goal"]["department"] == "support"
    assert result["execution_status"] == "NOT_CERTIFIED"
    assert result["business_outcome"] == "NOT_MEASURED"
    assert calls == ["analyze", "general_goal_service", "persist_draft"]
