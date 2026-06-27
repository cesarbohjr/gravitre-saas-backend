from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dependency_impact_service import (
    ENTITY_CONNECTOR,
    SCOPE_NOTE,
    build_scope_note,
    DependencyImpactService,
)


@pytest.mark.asyncio
async def test_direct_dependents_traced_from_real_fks():
    service = DependencyImpactService(settings=MagicMock())
    client = MagicMock()

    def _table(name: str):
        table = MagicMock()
        if name == "connectors":
            table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "conn-1", "type": "hubspot", "name": "HubSpot"}]
            )
        elif name == "workflow_nodes":
            table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "node-1",
                        "workflow_id": "wf-1",
                        "title": "Fetch CRM",
                        "node_type": "connector",
                        "connector_id": "conn-1",
                    }
                ]
            )
        elif name == "agents":
            table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        elif name == "org_entity_relationships":
            table.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )
        return table

    client.table.side_effect = _table
    with patch.object(service, "_client", return_value=client):
        direct = await service._find_direct_dependents("org-1", ENTITY_CONNECTOR, "conn-1")
    assert direct
    assert direct[0]["relationship"] == "workflow_nodes.connector_id FK"


@pytest.mark.asyncio
async def test_one_hop_limit_enforced():
    service = DependencyImpactService(settings=MagicMock())
    direct = [
        {
            "entityType": "workflow",
            "entityId": "wf-1",
            "label": "Pipeline",
            "relationship": "agents.systems includes connector type",
            "source": {},
        }
    ]
    indirect = [
        {
            "entityType": "workflow_schedule",
            "entityId": "sched-1",
            "label": "Daily",
            "relationship": "workflow_schedules.workflow_id FK",
            "source": {},
        }
    ]
    with patch.object(service, "_find_direct_dependents", new=AsyncMock(side_effect=[direct, indirect])):
        with patch.object(service, "_find_one_hop_further", new=AsyncMock(return_value=indirect)):
            with patch.object(service, "_find_dynamic_connector_usage", new=AsyncMock(return_value=[])):
                with patch.object(service, "_get_active_schedule", new=AsyncMock(return_value=None)):
                    report = await service.estimate_removal_impact("org-1", "connector", "conn-1")
    assert report["directImpact"]["declared"][0]["entityId"] == "wf-1"
    assert report["directImpact"]["declared"][0]["willFailAtNextRun"] is False
    assert report["indirectImpactOneHop"] == indirect


@pytest.mark.asyncio
async def test_every_report_includes_scope_note():
    service = DependencyImpactService(settings=MagicMock())
    with patch.object(service, "_find_direct_dependents", new=AsyncMock(return_value=[])):
        with patch.object(service, "_find_one_hop_further", new=AsyncMock(return_value=[])):
            with patch.object(service, "_find_dynamic_connector_usage", new=AsyncMock(return_value=[])):
                report = await service.estimate_removal_impact("org-1", "connector", "conn-1")
    assert report["scopeNote"] == build_scope_note()


@pytest.mark.asyncio
async def test_nl_parsing_only_identifies_entity_not_impact():
    service = DependencyImpactService(settings=MagicMock())
    client = MagicMock()

    def _table(name: str):
        table = MagicMock()
        if name == "connectors":
            table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "conn-1", "type": "hubspot", "name": "HubSpot Production"}]
            )
        else:
            table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        return table

    client.table.side_effect = _table
    with patch.object(service, "_client", return_value=client):
        with patch.object(
            service,
            "estimate_removal_impact",
            new=AsyncMock(
                return_value={
                    "scopeNote": build_scope_note(),
                    "directImpact": {"declared": [], "observedInExecutionHistory": []},
                    "indirectImpactOneHop": [],
                }
            ),
        ) as impact_mock:
            with patch.object(service, "_llm_identify_entity_only", new=AsyncMock()) as llm_mock:
                await service.answer_dependency_question("org-1", "what happens if we disconnect hubspot?")
    llm_mock.assert_not_awaited()
    impact_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_disconnecting_connector_surfaces_dependent_workflows():
    service = DependencyImpactService(settings=MagicMock())
    with patch.object(
        service,
        "_find_direct_dependents",
        new=AsyncMock(
            return_value=[
                {
                    "entityType": "workflow_node",
                    "entityId": "node-1",
                    "label": "CRM step",
                    "relationship": "workflow_nodes.connector_id FK",
                    "source": {"workflow_id": "wf-1"},
                }
            ]
        ),
    ):
        with patch.object(service, "_find_one_hop_further", new=AsyncMock(return_value=[])):
            with patch.object(service, "_find_dynamic_connector_usage", new=AsyncMock(return_value=[])):
                with patch.object(
                    DependencyImpactService,
                    "_get_active_schedule",
                    new=AsyncMock(return_value={"next_run_at": "2026-06-08T10:00:00+00:00"}),
                ):
                    report = await service.estimate_removal_impact("org-1", "connector", "conn-1")
    assert any(
        item["source"].get("workflow_id") == "wf-1"
        for item in report["directImpact"]["declared"]
    )
    assert report["directImpact"]["declared"][0]["nextScheduledRun"] == "2026-06-08T10:00:00+00:00"


def test_no_financial_or_staffing_estimation_attempted():
    import app.services.dependency_impact_service as module
    import inspect

    source = inspect.getsource(module.DependencyImpactService).lower()
    assert "estimate_revenue" not in source
    assert "estimate_staffing" not in source
    assert "digital twin" not in source
    assert "financial_impact" not in source


@pytest.mark.asyncio
async def test_dynamic_usage_found_from_execution_logs():
    service = DependencyImpactService(settings=MagicMock())
    client = MagicMock()
    since_rows = {
        "agent_decision_transparency_logs": [
            {
                "id": "log-1",
                "workflow_run_id": "run-1",
                "input_context": {"agentId": "agent-1"},
                "tools_invoked": [{"connectorId": "conn-1", "action": "hubspot.deals.get"}],
            }
        ],
        "agent_jobs": [
            {
                "id": "job-1",
                "payload": {"agent_id": "agent-2"},
                "result": {
                    "tool_calls": [
                        {"tool": "hubspot_update_deal", "result": {"connector_id": "conn-1", "success": True}}
                    ]
                },
            }
        ],
    }

    def _table(name: str):
        table = MagicMock()
        if name == "agent_decision_transparency_logs":
            table.select.return_value.eq.return_value.gte.return_value.limit.return_value.execute.return_value = MagicMock(
                data=since_rows["agent_decision_transparency_logs"]
            )
        elif name == "agent_jobs":
            table.select.return_value.eq.return_value.eq.return_value.gte.return_value.limit.return_value.execute.return_value = MagicMock(
                data=since_rows["agent_jobs"]
            )
        return table

    client.table.side_effect = _table
    with patch.object(service, "_client", return_value=client):
        observed = await service._find_dynamic_connector_usage("org-1", "conn-1", lookback_days=30)
    assert len(observed) == 2
    assert observed[0]["source"]["transparencyLogIds"] or observed[0]["source"]["agentJobIds"]


@pytest.mark.asyncio
async def test_declared_and_observed_dependencies_clearly_separated():
    service = DependencyImpactService(settings=MagicMock())
    declared = [{"entityType": "agent", "entityId": "agent-static", "label": "Static", "relationship": "agents.systems", "source": {}}]
    observed = [{"entityType": "agent", "entityId": "agent-dynamic", "label": "Dynamic", "invocationCount": 2, "relationship": "agent_jobs.result.tool_calls connector usage", "source": {"agentJobIds": ["job-1"], "transparencyLogIds": [], "lookbackDays": 90}}]
    with patch.object(service, "_find_direct_dependents", new=AsyncMock(return_value=declared)):
        with patch.object(service, "_find_one_hop_further", new=AsyncMock(return_value=[])):
            with patch.object(service, "_find_dynamic_connector_usage", new=AsyncMock(return_value=observed)):
                report = await service.estimate_removal_impact("org-1", "connector", "conn-1")
    assert report["directImpact"]["declared"] == declared
    assert report["directImpact"]["observedInExecutionHistory"] == observed


@pytest.mark.asyncio
async def test_lookback_window_respected():
    service = DependencyImpactService(settings=MagicMock())
    client = MagicMock()
    transparency_gte = MagicMock()
    jobs_gte = MagicMock()
    transparency_gte.limit.return_value.execute.return_value = MagicMock(data=[])
    jobs_gte.limit.return_value.execute.return_value = MagicMock(data=[])

    def _table(name: str):
        table = MagicMock()
        if name == "agent_decision_transparency_logs":
            table.select.return_value.eq.return_value.gte = transparency_gte
        elif name == "agent_jobs":
            table.select.return_value.eq.return_value.eq.return_value.gte = jobs_gte
        return table

    client.table.side_effect = _table
    with patch.object(service, "_client", return_value=client):
        await service._find_dynamic_connector_usage("org-1", "conn-1", lookback_days=14)
    assert transparency_gte.called
    assert jobs_gte.called
    since_arg = transparency_gte.call_args.args[1] if len(transparency_gte.call_args.args) > 1 else transparency_gte.call_args.args[0]
    parsed = datetime.fromisoformat(str(since_arg).replace("Z", "+00:00"))
    assert parsed <= datetime.now(timezone.utc) - timedelta(days=13)


def test_scope_note_updated_to_mention_execution_history_limitation():
    note = build_scope_note(90)
    assert "observedInExecutionHistory" in note or "observed" in note.lower()
    assert "90" in note


@pytest.mark.asyncio
async def test_still_one_hop_bounded():
    service = DependencyImpactService(settings=MagicMock())
    with patch.object(service, "_find_direct_dependents", new=AsyncMock(return_value=[])) as direct_mock:
        with patch.object(service, "_find_one_hop_further", new=AsyncMock(return_value=[])) as hop_mock:
            with patch.object(
                service,
                "_find_dynamic_connector_usage",
                new=AsyncMock(return_value=[{"entityType": "agent", "entityId": "a1"}]),
            ):
                report = await service.estimate_removal_impact("org-1", "connector", "conn-1")
    hop_mock.assert_awaited_once()
    assert hop_mock.await_args.args[1] == []
    assert report["indirectImpactOneHop"] == []
