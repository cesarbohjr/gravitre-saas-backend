"""MKT-AUDIT-5.4: Browse visibility rules."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.browse import MarketplaceBrowseError, get_marketplace_asset, list_marketplace_assets


def _table(rows: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.or_.return_value = mock
    mock.order.return_value = mock
    mock.range.return_value = mock
    mock.limit.return_value = mock
    mock.in_.return_value = mock
    mock.execute.return_value = MagicMock(data=rows or [], count=len(rows or []))
    return mock


@patch("app.marketplace.browse.validate_connectors_for_asset", return_value={"can_install": True, "checklist": []})
def test_public_assets_visible_to_all_orgs(mock_validate):
    public_row = {
        "id": "a1",
        "slug": "public-agent",
        "title": "Public",
        "asset_type": "ai_agent",
        "tags": [],
        "visibility": "public",
        "status": "published",
        "required_connectors": [],
        "install_count": 0,
        "clone_count": 0,
        "review_count": 0,
    }
    assets = _table([public_row])
    installs = _table([])

    client = MagicMock()
    client.table.side_effect = lambda name: installs if name == "marketplace_installs" else assets

    result = list_marketplace_assets(client, "org-other")
    assert result["total"] >= 1
    assert assets.or_.called
    filter_arg = assets.or_.call_args.args[0]
    assert "visibility.eq.public" in filter_arg
    assert "visibility.eq.internal" in filter_arg


def test_internal_assets_visible_to_owning_org():
    row = {
        "id": "a2",
        "slug": "internal-agent",
        "title": "Internal",
        "asset_type": "ai_agent",
        "tags": [],
        "visibility": "internal",
        "status": "published",
        "org_id": "org-a",
        "required_connectors": [],
        "config": {},
        "install_variables": [],
        "required_permissions": [],
    }
    with patch(
        "app.marketplace.browse.validate_connectors_for_asset",
        return_value={"can_install": True, "checklist": [], "blockers": []},
    ):
        detail = get_marketplace_asset(
            MagicMock(
                table=lambda name: _table(
                    [row] if name == "marketplace_assets" else []
                )
            ),
            "org-a",
            "internal-agent",
        )
    assert detail["asset"]["slug"] == "internal-agent"


def test_internal_assets_hidden_from_other_orgs():
    row = {
        "id": "a2",
        "slug": "internal-agent",
        "title": "Internal",
        "asset_type": "ai_agent",
        "tags": [],
        "visibility": "internal",
        "status": "published",
        "org_id": "org-a",
        "required_connectors": [],
        "config": {},
        "install_variables": [],
        "required_permissions": [],
    }
    assets = _table([row])
    client = MagicMock()
    client.table.return_value = assets

    with pytest.raises(MarketplaceBrowseError) as exc:
        get_marketplace_asset(client, "org-b", "internal-agent")
    assert exc.value.code == "NOT_FOUND"


def test_private_draft_assets_never_in_browse_results():
    assets = _table([])
    installs = _table([])
    client = MagicMock()
    client.table.side_effect = lambda name: installs if name == "marketplace_installs" else assets

    with patch(
        "app.marketplace.browse.validate_connectors_for_asset",
        return_value={"can_install": True, "checklist": []},
    ):
        list_marketplace_assets(client, "org-a")

    assets.eq.assert_any_call("status", "published")
