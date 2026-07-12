"""Part D P5: intelligence_pack install via install_asset (STA-310)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.service import MarketplaceError, install_asset

ASSET_ID = "44444444-4444-4444-4444-444444444444"


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


def _intelligence_pack_asset() -> dict:
    return {
        "id": ASSET_ID,
        "slug": "marketing-intelligence-pack",
        "asset_type": "intelligence_pack",
        "status": "published",
        "visibility": "public",
        "current_version": 1,
        "install_count": 0,
        "required_connectors": [],
        "install_variables": [{"key": "agentId", "label": "Agent ID", "required": True}],
        "config": {
            "department": "marketing",
            "default_subdomain": "content_marketing",
            "assignments": [
                {
                    "source_type": "google_drive_folder",
                    "source_id": "brand-guidelines",
                    "label": "Brand Guidelines",
                    "department": "marketing",
                }
            ],
        },
    }


@patch("app.marketplace.service.write_audit_event")
@patch("app.marketplace.service.increment_marketplace_counter")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
@patch("app.marketplace.entitlements.assert_install_entitlement")
@patch(
    "app.marketplace.intelligence_packs.install.install_intelligence_pack",
    return_value={
        "pack_id": "marketing-intelligence-pack",
        "assignments": [{"id": "asg-1"}],
        "count": 1,
    },
)
def test_install_asset_intelligence_pack_branch(
    mock_install_pack,
    _entitlement,
    _plan,
    _counter,
    _audit,
):
    asset = _intelligence_pack_asset()
    assets = _table([asset])
    installs = _table([])
    connectors = _table([])

    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_installs":
            return installs
        if name == "connectors":
            return connectors
        return _table([])

    client.table.side_effect = table

    result = install_asset(
        client,
        "org-1",
        ASSET_ID,
        actor_id="admin-1",
        install_variables={"agentId": "agent-99"},
    )
    assert result["installed"] is True
    assert result["assetType"] == "intelligence_pack"
    mock_install_pack.assert_called_once()
    assert mock_install_pack.call_args.args[2] == "agent-99"
    assert mock_install_pack.call_args.args[3] == "marketing-intelligence-pack"
    assert mock_install_pack.call_args.kwargs.get("asset_id") == ASSET_ID
    assert result["entities"]["entityId"] == ASSET_ID


@patch("app.marketplace.entitlements.assert_install_entitlement")
@patch("app.marketplace.service.get_plan_for_org", return_value={"agents_limit": None, "workflows_limit": None})
def test_install_asset_intelligence_pack_requires_agent_id(_plan, _entitlement):
    asset = _intelligence_pack_asset()
    client = MagicMock()
    client.table.side_effect = lambda name: _table([asset] if name == "marketplace_assets" else [])

    with pytest.raises(MarketplaceError) as exc:
        install_asset(client, "org-1", ASSET_ID, actor_id="admin-1", install_variables={})
    assert exc.value.code in {"VALIDATION_ERROR", "INSTALL_VARIABLES_INVALID"}
