"""MKT-7.1: MarketplaceService.install_asset()."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.service import MarketplaceError, install_asset, preview_install, validate_connectors_for_asset
from app.workflows.constants import SCHEMA_VERSION


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.update.return_value = mock
    mock.insert.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])
    mock.upsert.return_value = mock
    return mock


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


@patch("app.marketplace.service.write_audit_event")
@patch("app.marketplace.service.create_operator")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_install_ai_agent_uses_create_operator(mock_plan, mock_create_operator, mock_audit):
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
        return _table([])

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
    mock_create_operator.assert_called_once()
    payload = mock_create_operator.call_args.args[2]
    assert payload["name"] == "Lead Qualifier Agent"
    assert payload["status"] == "active"
    assert "id" in payload
    mock_audit.assert_called_once()


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
                    "config": {"action": "hubspot.search_contacts"},
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
        return _table([])

    client.table.side_effect = table

    with patch("app.marketplace.service.write_audit_event"):
        result = install_asset(client, "org-1", ASSET_ID, actor_id="user-1")

    assert result["entities"]["entityType"] == "workflow"
    mock_version.assert_called_once()


def test_preview_install_reports_blockers():
    asset = _published_agent_asset()
    assets = _table([asset])
    connectors = _table([])
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else connectors

    preview = preview_install(client, "org-1", ASSET_ID)
    assert preview["canInstall"] is False
    assert preview["blockers"]
