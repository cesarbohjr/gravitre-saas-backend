"""MKT-7.1: MarketplaceService.install_asset()."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.service import MarketplaceError, install_asset, preview_install, validate_connectors_for_asset
from app.workflows.constants import SCHEMA_VERSION
from tests.marketplace.conftest import marketplace_table_mock as _table


ASSET_ID = "11111111-1111-1111-1111-111111111111"


def _published_agent_asset() -> dict:
    return {
        "id": ASSET_ID,
        "slug": "lead-qualifier-agent",
        "asset_type": "ai_agent",
        "status": "published",
        "visibility": "public",
        "current_version": 1,
        "install_count": 0,
        "config": {
            "name": "Lead Qualifier Agent",
            "purpose": "Scores inbound leads",
            "role": "Sales Development",
            "systems": ["hubspot"],
            "seed_label": "agent:lead-qualifier",
        },
        "required_connectors": [
            {"connectorType": "hubspot", "label": "HubSpot", "required": True},
        ],
        "install_variables": [],
    }


def test_validate_connectors_returns_blockers():
    connectors = _table([{"type": "slack"}])
    client = MagicMock()
    client.table.side_effect = lambda name: connectors if name == "connectors" else _table([])

    result = validate_connectors_for_asset(
        client,
        "org-1",
        [{"connectorType": "hubspot", "label": "HubSpot", "required": True}],
    )
    assert result["can_install"] is False
    assert result["blockers"][0]["connector"] == "hubspot"
    assert result["blockers"][0]["action_url"]


@patch("app.marketplace.service._notify_asset_installed")
@patch("app.marketplace.service.write_audit_event")
@patch("app.marketplace.service.create_operator")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_install_ai_agent_uses_create_operator(mock_plan, mock_create_operator, mock_audit, mock_notify):
    mock_create_operator.return_value = {"id": "operator-1", "name": "Lead Qualifier Agent"}
    asset = _published_agent_asset()
    assets = _table([asset])
    connectors = _table([{"type": "hubspot", "id": "conn-1"}])
    installs = _table([])
    agents = _table([])
    operators = _table([])

    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "connectors":
            return connectors
        if name == "marketplace_installs":
            return installs
        if name == "agents":
            return agents
        if name == "operators":
            return operators
        return _table()

    client.table.side_effect = table

    result = install_asset(
        client,
        "org-1",
        ASSET_ID,
        actor_id="user-1",
        environment_name="production",
    )

    assert result["installed"] is True
    assert result["entities"]["operatorId"] == "operator-1"
    assert result.get("slug") == "lead-qualifier-agent"
    assert isinstance(result["deepLinks"], list)
    assert any(link.get("path") == "/agents/operator-1" for link in result["deepLinks"])
    mock_create_operator.assert_called_once()
    payload = mock_create_operator.call_args.args[2]
    assert payload["name"] == "Lead Qualifier Agent"
    assert payload["status"] == "active"
    assert "id" in payload
    mock_audit.assert_called_once()
    mock_notify.assert_called_once()


@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_install_blocks_when_connectors_missing(mock_plan):
    asset = _published_agent_asset()
    assets = _table([asset])
    connectors = _table([])
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else connectors

    with pytest.raises(MarketplaceError) as exc:
        install_asset(client, "org-1", ASSET_ID, actor_id="user-1")
    assert exc.value.code == "CONNECTORS_NOT_READY"
    assert exc.value.blockers


@patch("app.marketplace.service.ensure_active_workflow_version", return_value="version-1")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_install_workflow_writes_workflow_defs(mock_plan, mock_version):
    asset = {
        **_published_agent_asset(),
        "asset_type": "workflow",
        "slug": "hubspot-lead-qualification",
        "required_connectors": [],
        "config": {
            "schema_version": SCHEMA_VERSION,
            "name": "HubSpot Lead Qualification",
            "description": "Qualify inbound leads",
            "steps": [
                {
                    "id": "lookup",
                    "name": "HubSpot lookup",
                    "type": "invoke_tool",
                    "config": {"action": "hubspot.contacts.search"},
                }
            ],
        },
    }
    assets = _table([asset])
    workflow_defs = _table([])
    workflows = _table([])
    installs = _table([])

    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "workflow_defs":
            return workflow_defs
        if name == "workflows":
            return workflows
        if name == "marketplace_installs":
            return installs
        return _table()

    client.table.side_effect = table

    with patch("app.marketplace.service.write_audit_event"):
        result = install_asset(client, "org-1", ASSET_ID, actor_id="user-1")

    assert result["entities"]["entityType"] == "workflow"
    mock_version.assert_called_once()


@patch("app.marketplace.service.create_operator")
@patch("app.marketplace.service.ensure_active_workflow_version", return_value="version-1")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_install_workflow_provisions_companion_agents(mock_plan, mock_version, mock_create_operator):
    mock_create_operator.side_effect = lambda *_a, **_k: {
        "id": _a[2]["id"],
        "name": _a[2]["name"],
    }
    asset = {
        "id": ASSET_ID,
        "slug": "competitive-intelligence-monitoring",
        "asset_type": "workflow",
        "status": "published",
        "visibility": "public",
        "current_version": 1,
        "title": "Competitive Intelligence Monitoring",
        "department": "Marketing",
        "required_connectors": [],
        "install_variables": [],
        "config": {
            "schema_version": SCHEMA_VERSION,
            "name": "Competitive Intelligence Monitoring",
            "description": "Automated competitive intelligence monitoring playbook.",
            "steps": [
                {
                    "id": "scan",
                    "name": "Competitive scan",
                    "type": "agent",
                    "metadata": {
                        "agent_seed": "agent:competitor-research-agent",
                        "task": "Summarize competitor moves.",
                    },
                },
                {
                    "id": "brief",
                    "name": "Marketing brief",
                    "type": "agent",
                    "metadata": {
                        "agent_seed": "agent:marketing-analyst",
                        "task": "Translate intel into campaign actions.",
                    },
                },
            ],
        },
    }
    assets = _table([asset])
    agents = _table([])
    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "agents":
            return agents
        if name == "marketplace_installs":
            return _table()
        return _table()

    client.table.side_effect = table

    with patch("app.marketplace.service.write_audit_event"), patch(
        "app.marketplace.service.upsert_agent_tool_permission"
    ):
        result = install_asset(client, "org-1", ASSET_ID, actor_id="user-1")

    assert result["entities"]["entityType"] == "workflow"
    assert len(result["entities"].get("agentIds") or []) == 2
    assert mock_create_operator.call_count == 2
    created_configs = [call.args[2]["config"] for call in mock_create_operator.call_args_list]
    slugs = {str(cfg.get("marketplaceSlug") or cfg.get("slug") or "") for cfg in created_configs}
    assert "competitor-research-agent" in slugs
    assert "marketing-analyst" in slugs


def test_preview_install_reports_blockers():
    asset = _published_agent_asset()
    assets = _table([asset])
    connectors = _table([])
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else connectors

    preview = preview_install(client, "org-1", ASSET_ID)
    assert preview["canInstall"] is False
    assert preview["blockers"]


@patch("app.marketplace.entitlements.get_entitlement_status")
def test_preview_install_blocks_without_entitlement(mock_entitlement):
    asset = _published_agent_asset()
    asset["org_id"] = "publisher-org"
    asset["pricing_type"] = "paid"
    asset["price_cents"] = 9900
    assets = _table([asset])
    connectors = _table([])
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else connectors
    mock_entitlement.return_value = {
        "requiresPayment": True,
        "hasEntitlement": False,
        "pricingType": "paid",
        "priceCents": 9900,
        "currency": "usd",
    }

    preview = preview_install(client, "buyer-org", ASSET_ID)
    assert preview["canInstall"] is False
    assert preview["requiresPayment"] is True
    assert any(blocker.get("connector") == "payment" for blocker in preview["blockers"])


@patch("app.marketplace.service.ensure_active_workflow_version", return_value="version-1")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_install_marketplace_play_uses_canonical_play_runtime(mock_plan, mock_version):
    asset = {
        "id": ASSET_ID,
        "slug": "client-risk-radar-play",
        "title": "Client Risk Radar",
        "asset_type": "play",
        "status": "published",
        "visibility": "public",
        "current_version": 1,
        "install_count": 0,
        "required_connectors": [],
        "install_variables": [],
        "config": {
            "key": "client-risk-radar",
            "name": "Client Risk Radar",
            "description": "Identify accounts that need intervention.",
            "trigger": {"type": "scheduled"},
            "workflow_steps": [
                {
                    "id": "analyze",
                    "name": "Analyze account risk",
                    "type": "agent",
                    "metadata": {"task": "Review current risk signals."},
                }
            ],
            "outcome_events": ["client_risk_detected"],
            "kpi_keys": ["customer_health"],
            "approvals": [],
            "verification": {"mode": "source_of_record"},
        },
    }
    assets = _table([asset])
    installs = _table([])
    play_installations = _table()
    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_installs":
            return installs
        if name == "play_installations":
            return play_installations
        return _table()

    client.table.side_effect = table

    with patch("app.marketplace.service.write_audit_event"), patch(
        "app.marketplace.service._notify_asset_installed"
    ), patch(
        "app.plays.workflow_bindings.bind_play_to_workflow",
        return_value={
            "workflowId": "wf-1",
            "play": {"key": "client-risk-radar", "version": "1"},
            "executionAuthority": "canonical_workflow_runtime",
        },
    ) as bind:
        result = install_asset(client, "org-1", ASSET_ID, actor_id="user-1")

    assert result["entities"]["entityType"] == "play"
    assert result["entities"]["playKey"] == "client-risk-radar"
    assert result["entities"]["operatingMode"] == "OBSERVE"
    assert result["entities"]["executionAuthority"] == "canonical_workflow_runtime"
    assert any(link.get("path") == "/plays?play=client-risk-radar" for link in result["deepLinks"])
    bind.assert_called_once()
    payload = play_installations.upsert.call_args.args[0]
    assert payload["operating_mode"] == "OBSERVE"
    assert payload["configuration"]["outcomeEvents"] == ["client_risk_detected"]


@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_install_outcome_pack_materializes_all_required_components(mock_plan):
    play_keys = [
        "intelligent-ticket-intake",
        "resolution-copilot",
        "sla-rescue",
        "stale-ticket-recovery",
        "recurring-problem-hunter",
        "client-communication-manager",
    ]
    asset = {
        "id": ASSET_ID,
        "slug": "msp-service-desk-3",
        "title": "MSP Service Desk 3.0",
        "asset_type": "outcome_pack",
        "status": "published",
        "visibility": "public",
        "current_version": 1,
        "install_count": 0,
        "required_connectors": [],
        "install_variables": [],
        "config": {
            "marketplace_version": "3.0",
            "outcome_contract": {
                "problem": "Service desks lose time to manual triage and stalled work.",
                "target_outcome": "Reduce response and resolution time while improving SLA performance.",
                "success_criteria": ["All required Plays install and emit measurable outcomes."],
                "outcome_events": ["service_desk_outcome_verified"],
                "kpis": [
                    {"key": "mtta", "label": "MTTA", "unit": "minutes", "direction": "decrease"},
                    {"key": "mttr", "label": "MTTR", "unit": "minutes", "direction": "decrease"},
                    {"key": "sla_compliance", "label": "SLA compliance", "unit": "percent", "direction": "increase"},
                ],
                "verification_required": True,
            },
            "agents": [
                {
                    "name": "Service Desk Coordinator",
                    "purpose": "Coordinates service desk operating work.",
                    "seed_label": "agent:service-desk-coordinator",
                }
            ],
            "plays": [
                {
                    "key": key,
                    "name": key.replace("-", " ").title(),
                    "description": "Execute a measurable service desk operating outcome.",
                    "trigger": {"type": "manual"},
                    "workflow_steps": [
                        {
                            "id": f"{key}-step",
                            "name": "Analyze",
                            "type": "agent",
                            "metadata": {
                                "agent_seed": "agent:service-desk-coordinator",
                                "task": "Analyze the service desk signal.",
                            },
                        }
                    ],
                    "outcome_events": [f"{key}_completed"],
                    "kpi_keys": ["mtta"],
                    "verification": {"mode": "source_of_record"},
                }
                for key in play_keys
            ],
            "knowledge": [],
            "dataset": {
                "entities": [
                    {
                        "name": "tickets",
                        "source": "psa",
                        "primary_key": "id",
                        "fields": ["id", "status", "priority"],
                    }
                ],
                "metrics": [
                    {"key": "mtta", "label": "MTTA", "formula": "avg(first_response_at-created_at)", "unit": "minutes"}
                ],
            },
            "dashboard": {
                "title": "Service Desk Outcomes",
                "metrics": [
                    {"kpi_key": "mtta", "label": "MTTA", "visualization": "trend"},
                    {"kpi_key": "mttr", "label": "MTTR", "visualization": "trend"},
                    {"kpi_key": "sla_compliance", "label": "SLA compliance", "visualization": "progress"},
                ],
                "refresh_mode": "event",
            },
            "skills": ["ticket-triage"],
        },
    }
    assets = _table([asset])
    installs = _table([])
    dataset_installs = _table()
    dashboard_installs = _table()
    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_dataset_pack_installations":
            return dataset_installs
        if name == "marketplace_dashboard_pack_installations":
            return dashboard_installs
        return _table()

    client.table.side_effect = table

    play_results = [
        {
            "entityType": "play",
            "entityId": f"play-inst-{idx}",
            "playKey": key,
            "playVersion": "1",
            "playInstallationId": f"play-inst-{idx}",
            "workflowId": f"wf-{idx}",
            "workflowIds": [f"wf-{idx}"],
            "operatingMode": "OBSERVE",
            "executionAuthority": "canonical_workflow_runtime",
        }
        for idx, key in enumerate(play_keys)
    ]

    with patch("app.marketplace.service.write_audit_event"), patch(
        "app.marketplace.service._notify_asset_installed"
    ), patch(
        "app.marketplace.service._install_ai_agent",
        return_value={"entityType": "operator", "entityId": "agent-1", "operatorId": "agent-1"},
    ), patch(
        "app.marketplace.service._install_play_asset",
        side_effect=play_results,
    ) as install_play:
        result = install_asset(client, "org-1", ASSET_ID, actor_id="user-1")

    assert result["installed"] is True
    assert result["entities"]["entityType"] == "outcome_pack"
    assert result["entities"]["marketplaceVersion"] == "3.0"
    assert len(result["entities"]["plays"]) == 6
    assert len(result["entities"]["workflowIds"]) == 6
    assert result["entities"]["datasetPackId"]
    assert result["entities"]["dashboardPackId"]
    assert result["entities"]["executionAuthority"] == "canonical_workflow_runtime"
    assert install_play.call_count == 6
    dataset_installs.upsert.assert_called_once()
    dashboard_installs.upsert.assert_called_once()
