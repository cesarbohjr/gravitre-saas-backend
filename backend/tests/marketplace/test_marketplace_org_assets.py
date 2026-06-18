"""MKT-AUDIT-9.3 / 6.7: Org-owned asset listing and internal browse filter."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.marketplace.browse import list_marketplace_assets
from app.marketplace.crud import list_org_assets

ORG_ID = "org-11111111-1111-1111-1111-111111111111"


def _table(*, data=None, count=0):
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.neq.return_value = mock
    mock.or_.return_value = mock
    mock.order.return_value = mock
    mock.range.return_value = mock
    result = MagicMock(data=data or [], count=count)
    mock.execute.return_value = result
    return mock


def test_list_org_assets_filters_by_status():
    assets = _table(
        data=[
            {
                "id": "a1",
                "slug": "draft-agent",
                "title": "Draft Agent",
                "asset_type": "ai_agent",
                "status": "pending_review",
                "org_id": ORG_ID,
            }
        ],
        count=1,
    )
    client = MagicMock()
    client.table.return_value = assets

    result = list_org_assets(client, ORG_ID, status="pending_review")
    assert result["total"] == 1
    assert result["assets"][0]["slug"] == "draft-agent"


def test_browse_internal_visibility_filter():
    assets = _table(count=0)
    client = MagicMock()
    client.table.return_value = assets

    list_marketplace_assets(client, ORG_ID, visibility="internal", limit=10)
    assets.eq.assert_any_call("visibility", "internal")
    assets.eq.assert_any_call("org_id", ORG_ID)
