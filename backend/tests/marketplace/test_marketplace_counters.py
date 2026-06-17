"""MKT-10.1: Atomic marketplace counter increments."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.counters import increment_marketplace_counter


def test_increment_install_count_uses_rpc():
    rpc = MagicMock()
    rpc.execute.return_value = MagicMock(data=42)
    client = MagicMock()
    client.rpc.return_value = rpc

    value = increment_marketplace_counter(
        client,
        "11111111-1111-1111-1111-111111111111",
        "install_count",
    )

    assert value == 42
    client.rpc.assert_called_once_with(
        "increment_marketplace_asset_counter",
        {
            "p_asset_id": "11111111-1111-1111-1111-111111111111",
            "p_counter": "install_count",
        },
    )


def test_increment_clone_count_uses_rpc():
    rpc = MagicMock()
    rpc.execute.return_value = MagicMock(data=7)
    client = MagicMock()
    client.rpc.return_value = rpc

    value = increment_marketplace_counter(
        client,
        "11111111-1111-1111-1111-111111111111",
        "clone_count",
    )

    assert value == 7
    client.rpc.assert_called_once_with(
        "increment_marketplace_asset_counter",
        {
            "p_asset_id": "11111111-1111-1111-1111-111111111111",
            "p_counter": "clone_count",
        },
    )


@patch("app.marketplace.counters._legacy_increment", return_value=11)
def test_falls_back_when_rpc_missing(mock_legacy):
    rpc = MagicMock()
    rpc.execute.side_effect = Exception("function increment_marketplace_asset_counter does not exist")
    client = MagicMock()
    client.rpc.return_value = rpc

    value = increment_marketplace_counter(client, "asset-1", "install_count")

    assert value == 11
    mock_legacy.assert_called_once_with(client, "asset-1", "install_count")


@patch("app.marketplace.service.increment_marketplace_counter")
@patch("app.marketplace.service.write_audit_event")
@patch("app.marketplace.service.create_operator")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_install_asset_bumps_counter_via_rpc(mock_plan, mock_create_operator, mock_audit, mock_increment):
    from app.marketplace.service import install_asset

    mock_create_operator.return_value = {"id": "operator-1", "name": "Lead Qualifier Agent"}
    asset_id = "11111111-1111-1111-1111-111111111111"
    asset = {
        "id": asset_id,
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
        },
        "required_connectors": [
            {"connectorType": "hubspot", "label": "HubSpot", "required": True},
        ],
        "install_variables": [],
    }

    def _table(name):
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.limit.return_value = mock
        mock.insert.return_value = mock
        mock.update.return_value = mock
        mock.upsert.return_value = mock
        if name == "marketplace_assets":
            mock.execute.return_value = MagicMock(data=[asset])
        elif name == "connectors":
            mock.execute.return_value = MagicMock(data=[{"type": "hubspot", "id": "conn-1"}])
        elif name == "marketplace_installs":
            mock.execute.return_value = MagicMock(data=[])
        else:
            mock.execute.return_value = MagicMock(data=[{"id": "test-id"}])
        return mock

    client = MagicMock()
    client.table.side_effect = _table

    install_asset(client, "org-1", asset_id, actor_id="user-1")

    mock_increment.assert_called_once_with(client, asset_id, "install_count")
