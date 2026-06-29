"""MKT-AUDIT-5.6: Structured plan limit errors on install."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.billing.entitlement_service import PlanLimitExceededError
from app.marketplace.service import install_asset

ASSET_ID = "11111111-1111-1111-1111-111111111111"


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])
    return mock


def _agent_asset() -> dict:
    return {
        "id": ASSET_ID,
        "slug": "lead-qualifier-agent",
        "asset_type": "ai_agent",
        "status": "published",
        "visibility": "public",
        "current_version": 1,
        "config": {
            "name": "Lead Qualifier Agent",
            "purpose": "Scores inbound leads",
            "role": "Sales Development",
            "systems": [],
        },
        "required_connectors": [],
        "install_variables": [],
    }


@patch("app.marketplace.service.list_operators", return_value=[{"id": "op-1"}, {"id": "op-2"}])
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": 2, "workflows_limit": 10})
def test_limit_exceeded_returns_structured_error(mock_plan, mock_operators):
    asset = _agent_asset()
    assets = _table([asset])
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else _table([])

    with pytest.raises(PlanLimitExceededError) as exc:
        install_asset(client, "org-1", ASSET_ID, actor_id="user-1")
    detail = exc.value.detail
    assert detail["error"] == "plan_limit_exceeded"
    assert detail["limit_type"] == "agent_count"
    assert detail["current"] == 2
    assert detail["max"] == 2


@patch("app.marketplace.service.list_operators", return_value=[{"id": "op-1"}, {"id": "op-2"}])
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": 2, "workflows_limit": 10})
def test_structured_error_includes_upgrade_path(mock_plan, mock_operators):
    asset = _agent_asset()
    assets = _table([asset])
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else _table([])

    with pytest.raises(PlanLimitExceededError) as exc:
        install_asset(client, "org-1", ASSET_ID, actor_id="user-1")
    assert exc.value.detail["upgrade_url"] == "/settings/billing"
