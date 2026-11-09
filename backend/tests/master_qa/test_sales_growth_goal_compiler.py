"""Goal-to-canvas certification: no fake tools, no unapproved writes, real schema."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.workflows.sales_growth_recipe import (
    GoalCompilationBlocked,
    compile_sales_growth_goal,
    verified_sales_observations,
)
from app.workflows.graph_model import build_execution_graph, topological_batches


def _entry(connector, action, kind="read", implemented=True):
    return SimpleNamespace(
        connector_id=connector, action_key=action,
        display_name=action, kind=kind,
        chat_executable=implemented,
        invoke_tool_handler=action if implemented else "",
        implementation_status="executable" if implemented else "not_implemented",
    )


def _compile(**extra):
    return compile_sales_growth_goal(
        goal="I need to increase sales",
        connected_integrations=["hubspot"],
        action_entries=[
            _entry("hubspot", "hubspot.deals.search"),
            _entry("hubspot", "hubspot.contacts.search"),
            _entry("hubspot", "hubspot.contacts.create", kind="write"),
            _entry("slack", "slack.channels.list"),
            _entry("google_analytics", "google_analytics.reports.run"),
        ],
        recognized_objective="increase_sales",
        **extra,
    )


def test_goal_compiles_to_actual_canvas_schema_and_registered_reads():
    plan = _compile()
    assert plan.objective == "increase_sales"
    assert plan.status == "READ_DIAGNOSTIC_READY"
    assert plan.observation_status == "NOT_RUN"
    assert plan.capabilities == ("hubspot.deals.search", "hubspot.contacts.search")
    assert plan.workflow_definition["steps"][0]["config"]["max_records"] == 250
    assert not plan.required_external_approval
    assert "slack.channels.list" not in plan.capabilities
    assert "hubspot.contacts.create" not in plan.capabilities
    graph = build_execution_graph(plan.graph["nodes"], plan.graph["edges"])
    assert topological_batches(graph) == [
        ["sales-goal-source"], ["sales-evidence-1"], ["sales-evidence-2"],
    ]
    assert [s["config"]["action"] for s in plan.workflow_definition["steps"]] == list(plan.capabilities)


@pytest.mark.parametrize("connected", [[], ["slack"], ["google_ads"], ["  "]])
def test_missing_connector_is_fail_closed(connected):
    with pytest.raises(GoalCompilationBlocked, match="no_connected_executable_sales_read"):
        compile_sales_growth_goal(
            goal="Increase sales", connected_integrations=connected,
            action_entries=[_entry("hubspot", "hubspot.contacts.search")],
            recognized_objective="increase_sales",
        )


def test_catalog_only_or_write_only_actions_never_become_executable():
    with pytest.raises(GoalCompilationBlocked):
        compile_sales_growth_goal(
            goal="increase sales", connected_integrations=["hubspot"],
            action_entries=[
                _entry("hubspot", "hubspot.contacts.search", implemented=False),
                _entry("hubspot", "hubspot.contacts.create", kind="write"),
            ],
            recognized_objective="increase_sales",
        )


def test_no_fabricated_play_or_workflow_id():
    plan = _compile(installed_plays=[
        {"status": "ready", "department": "sales", "play_key": "growth"},
        {"status": "ready", "department": "marketing", "play_key": "bad",
         "workflow_id": "not-sales", "installed": True},
    ], agent_selection={"persona_key": "SALES"})
    assert plan.selected_play is None and plan.selected_workflow_id is None
    assert plan.agent_persona == "SALES"


def test_reuse_only_positively_ready_tenant_installed_play():
    plan = _compile(installed_plays=[
        {"status": "ready", "department": "sales", "play_key": "sales-boost",
         "workflow_id": "installed-workflow-uuid", "installed": True},
    ])
    assert plan.selected_play == "sales-boost"
    assert plan.selected_workflow_id == "installed-workflow-uuid"


def test_observation_requires_matching_persisted_completed_steps():
    plan = _compile()
    assert verified_sales_observations(plan, completed_steps=[])["status"] == "INCOMPLETE"
    incomplete = [{"step_id": "sales-evidence-1", "status": "completed",
                   "output_snapshot": {"data": {"results": []}}}]
    assert verified_sales_observations(plan, completed_steps=incomplete)["status"] == "INCOMPLETE"
    completed = incomplete + [{"step_id": "sales-evidence-2", "status": "completed",
                               "output_snapshot": {"data": {"results": [{"id": "fixture"}]}}}]
    evidence = verified_sales_observations(plan, completed_steps=completed)
    assert evidence["status"] == "DIAGNOSTIC_READS_OBSERVED"
    assert len(evidence["verified_actions"]) == 2
    assert evidence["business_outcome"] == "NOT_MEASURED"
    completed[1]["status"] = "failed"
    assert verified_sales_observations(plan, completed_steps=completed)["status"] == "INCOMPLETE"


def test_non_sales_goal_does_not_silently_route_to_sales():
    with pytest.raises(GoalCompilationBlocked, match="requires_verified_semantic_objective"):
        compile_sales_growth_goal(
            goal="reduce support backlog", connected_integrations=["hubspot"],
            action_entries=[_entry("hubspot", "hubspot.contacts.search")],
        )


@pytest.mark.asyncio
async def test_authenticated_org_selection_uses_real_selector_boundary(monkeypatch):
    from app.services import agent_selector
    from app.workflows import sales_growth_recipe
    calls = []

    class TenantSelector:
        def __init__(self, settings):
            assert settings is not None
        async def select(self, org_id, classification):
            calls.append(("select", org_id, classification["department"]))
            return {"persona_key": "SALES"}
        async def _get_connected(self, org_id):
            calls.append(("connected", org_id))
            return {"hubspot", "platform"}

    monkeypatch.setattr(agent_selector, "AgentSelector", TenantSelector)
    monkeypatch.setattr(
        sales_growth_recipe, "build_connector_execution_matrix",
        lambda: (_entry("hubspot", "hubspot.contacts.search"),),
    )
    plan = await sales_growth_recipe.compile_sales_growth_for_org(
        org_id="tenant-123", goal="I need to increase sales", settings=object(),
        recognized_objective="increase_sales",
    )
    assert calls == [("select", "tenant-123", "sales"), ("connected", "tenant-123")]
    assert plan.capabilities == ("hubspot.contacts.search",)
    assert plan.agent_persona == "SALES"


@pytest.mark.asyncio
async def test_org_boundary_must_be_explicit():
    from app.workflows.sales_growth_recipe import compile_sales_growth_for_org
    with pytest.raises(GoalCompilationBlocked, match="authenticated_org_required"):
        await compile_sales_growth_for_org(
            org_id="", goal="increase sales", settings=object(),
        )


def test_installed_play_discovery_requires_same_org_environment_and_workflow_binding(monkeypatch):
    from app.workflows.sales_growth_recipe import discover_installed_sales_plays
    from app.workflows import repository
    from app.plays import workflow_bindings
    checks = []

    class Query:
        def select(self, *args):
            return self
        def eq(self, field, value):
            checks.append((field, value))
            return self
        def execute(self):
            return SimpleNamespace(data=[
                {"play_key": "qualified-prospecting", "status": "ready"},
                {"play_key": "revenue-recovery", "status": "paused"},
                {"play_key": "marketing-performance", "status": "ready"},
            ])

    monkeypatch.setattr(repository, "get_supabase_client",
                        lambda settings: SimpleNamespace(table=lambda name: Query()))
    monkeypatch.setattr(workflow_bindings, "list_all_play_workflow_bindings",
                        lambda client, org: {
                            "qualified-prospecting": [{
                                "workflowId": "tenant-bound-workflow", "status": "active",
                            }],
                            "marketing-performance": [],  # no binding
                        })
    plays = discover_installed_sales_plays(
        org_id="tenant-A", settings=object(), environment_name="synthetic",
    )
    assert plays == [{
        "play_key": "qualified-prospecting",
        "workflow_id": "tenant-bound-workflow", "department": "sales",
        "status": "ready", "installed": True,
    }]
    assert checks == [("org_id", "tenant-A"), ("environment_name", "synthetic")]


def test_unbound_analytics_schema_cannot_masquerade_as_executable_plan():
    with pytest.raises(GoalCompilationBlocked, match="no_connected_executable_sales_read"):
        compile_sales_growth_goal(
            goal="increase sales",
            connected_integrations=["google_analytics"],
            action_entries=[
                _entry("google_analytics", "google_analytics.reports.run"),
            ],
            recognized_objective="increase_sales",
        )


def _persisted_hubspot_read(*, step_id="sales-evidence-1", action="hubspot.deals.search",
                            complete=True, rows=None):
    results = rows if rows is not None else [{"id": "deal-1"}]
    return {
        "org_id": "org-A", "run_id": "run-1", "step_id": step_id,
        "status": "completed", "completed_at": "2026-11-08T20:00:00+00:00",
        "output_snapshot": {
            "action": action, "data": {
                "results": results,
                "coverage": {
                    "complete": complete,
                    "returned": len(results), "total_reported": len(results),
                },
            },
        },
    }


def test_persisted_hubspot_reads_produce_observed_census_not_revenue_forecast():
    from app.workflows.sales_growth_recipe import diagnose_persisted_sales_reads
    plan = _compile()
    result = diagnose_persisted_sales_reads(
        plan, org_id="org-A", run_id="run-1",
        completed_steps=[
            _persisted_hubspot_read(),
            _persisted_hubspot_read(
                step_id="sales-evidence-2", action="hubspot.contacts.search",
                rows=[{"id": "contact-1"}, {"id": "contact-2"}],
            ),
        ],
    )
    assert result["status"] == "OBSERVATIONS_AVAILABLE"
    assert {r["metric_key"] for r in result["observations"]} == {"deals_record_count"}
    assert any(f["status"] == "UNSUPPORTED_METRIC_EXTRACTION" for f in result["findings"])
    assert result["business_outcome"] == "NOT_MEASURED"
    assert result["recommended_writes"] == []
    assert result["hypotheses"] == []


def test_incomplete_hubspot_pages_never_claim_total():
    from app.workflows.sales_growth_recipe import diagnose_persisted_sales_reads
    result = diagnose_persisted_sales_reads(
        _compile(), org_id="org-A", run_id="run-1",
        completed_steps=[_persisted_hubspot_read(complete=False)],
    )
    assert result["status"] == "INSUFFICIENT_VERIFIED_EVIDENCE"
    assert result["observations"] == []
    assert result["findings"][0]["status"] == "PARTIAL_READ_NO_TOTAL"


@pytest.mark.parametrize("mutation", [
    {"org_id": "org-B"},
    {"run_id": "run-other"},
])
def test_hubspot_diagnostic_fails_closed_on_wrong_tenant_or_run(mutation):
    from app.workflows.sales_growth_recipe import diagnose_persisted_sales_reads
    step = _persisted_hubspot_read()
    step.update(mutation)
    with pytest.raises(GoalCompilationBlocked, match="persisted_step_tenant_or_run_mismatch"):
        diagnose_persisted_sales_reads(
            _compile(), org_id="org-A", run_id="run-1", completed_steps=[step],
        )


def test_hubspot_diagnostic_rejects_duplicate_step_ids_and_simulated_output():
    from app.workflows.sales_growth_recipe import diagnose_persisted_sales_reads
    step = _persisted_hubspot_read()
    with pytest.raises(GoalCompilationBlocked, match="duplicate_persisted_step_identity"):
        diagnose_persisted_sales_reads(
            _compile(), org_id="org-A", run_id="run-1", completed_steps=[step, step],
        )
    step["output_snapshot"]["simulated"] = True
    result = diagnose_persisted_sales_reads(
        _compile(), org_id="org-A", run_id="run-1", completed_steps=[step],
    )
    assert result["observations"] == []
    assert result["findings"][0]["status"] == "UNVERIFIED"


def test_hubspot_diagnostic_rejects_inconsistent_provider_coverage():
    from app.workflows.sales_growth_recipe import diagnose_persisted_sales_reads
    step = _persisted_hubspot_read()
    step["output_snapshot"]["data"]["coverage"]["total_reported"] = 8
    result = diagnose_persisted_sales_reads(
        _compile(), org_id="org-A", run_id="run-1", completed_steps=[step],
    )
    assert result["observations"] == []
    assert result["findings"][0]["status"] == "INCONSISTENT_PROVIDER_TOTAL"
