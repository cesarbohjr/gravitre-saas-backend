"""MKT-AUDIT-5.5: Department pack install coverage."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.service import install_asset
from app.workflows.constants import SCHEMA_VERSION

ASSET_ID = "22222222-2222-2222-2222-222222222222"


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.upsert.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])
    return mock


def _department_pack_asset() -> dict:
    return {
        "id": ASSET_ID,
        "slug": "marketing-operations-pack",
        "asset_type": "department_pack",
        "status": "published",
        "visibility": "public",
        "current_version": 1,
        "install_count": 0,
        "required_connectors": [],
        "install_variables": [],
        "config": {
            "workflow_name": "Marketing Ops Workflow",
            "workflow_description": "Ops automation",
            "agents": [
                {
                    "seed_label": "agent:marketing-analyst",
                    "name": "Marketing Analyst",
                    "purpose": "Analyze campaigns",
                    "role": "Analyst",
                    "department": "Marketing",
                    "systems": [],
                }
            ],
            "rag_sources": [
                {"seed_label": "rag:brand", "title": "Brand Guide", "type": "manual", "metadata": {}}
            ],
            "workflow_steps": [
                {"id": "overview", "name": "Overview", "type": "noop"},
            ],
        },
    }


@patch("app.marketplace.service.write_audit_event")
@patch("app.marketplace.service.increment_marketplace_counter")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
@patch("app.marketplace.service.create_operator", return_value={"id": "operator-1", "name": "Marketing Analyst"})
def test_install_creates_all_pack_items(mock_create_operator, mock_plan, mock_counter, mock_audit):
    asset = _department_pack_asset()
    assets = _table([asset])
    installs = _table([])
    agents = _table([])
    rag = _table([])
    workflows = _table([])
    workflow_defs = _table([])

    client = MagicMock()

    def table(name):
        mapping = {
            "marketplace_assets": assets,
            "marketplace_installs": installs,
            "agents": agents,
            "rag_sources": rag,
            "workflows": workflows,
            "workflow_defs": workflow_defs,
        }
        return mapping.get(name, _table([]))

    client.table.side_effect = table

    with patch("app.marketplace.service.ensure_active_workflow_version", return_value="ver-1"):
        result = install_asset(client, "org-1", ASSET_ID, actor_id="user-1")

    assert result["installed"] is True
    assert result["entities"]["entityType"] == "department_pack"
    assert result["entities"]["agentIds"]
    assert result["entities"]["workflowIds"]
    assert result["entities"]["ragSourceIds"]
    mock_counter.assert_called_once()


@patch("app.marketplace.service.write_audit_event")
@patch("app.marketplace.service.increment_marketplace_counter")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
@patch("app.marketplace.service.create_operator", side_effect=RuntimeError("agent failed"))
def test_partial_pack_failure_returns_summary_not_total_failure(
    mock_create_operator,
    mock_plan,
    mock_counter,
    mock_audit,
):
    asset = _department_pack_asset()
    assets = _table([asset])
    installs = _table([])
    rag = _table([])
    workflows = _table([])
    workflow_defs = _table([])

    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_installs":
            return installs
        if name == "rag_sources":
            return rag
        if name in {"workflows", "workflow_defs"}:
            return workflows if name == "workflows" else workflow_defs
        return _table([])

    client.table.side_effect = table

    with patch("app.marketplace.service.ensure_active_workflow_version", return_value="ver-1"):
        result = install_asset(client, "org-1", ASSET_ID, actor_id="user-1")

    assert result["installed"] is True
    assert result["entities"]["failures"]


@patch("app.marketplace.service.write_audit_event")
@patch("app.marketplace.service.list_operators", return_value=[{"id": "op-1"}, {"id": "op-2"}])
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": 2, "workflows_limit": 10})
def test_department_pack_agent_limit_raises_structured_error(mock_plan, mock_operators, mock_audit):
    asset = _department_pack_asset()
    assets = _table([asset])
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else _table([])

    from app.marketplace.service import MarketplaceError

    with pytest.raises(MarketplaceError) as exc:
        install_asset(client, "org-1", ASSET_ID, actor_id="user-1")
    assert exc.value.code == "LIMIT_EXCEEDED"
    assert exc.value.details["limit_type"] == "agent_count"
