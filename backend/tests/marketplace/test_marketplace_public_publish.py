"""MKT-AUDIT-11.2: Gravitre public review queue."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.publish import (
    MarketplacePublishError,
    approve_asset_for_public_publish,
    list_public_review_queue,
    submit_asset_for_public_review,
)

ORG_ID = "org-11111111-1111-1111-1111-111111111111"


def _asset_row(**overrides):
    row = {
        "id": "asset-1",
        "slug": "public-agent",
        "title": "Public Agent",
        "asset_type": "ai_agent",
        "status": "draft",
        "review_scope": "internal",
        "org_id": ORG_ID,
        "config": {},
        "required_connectors": [],
        "install_variables": [],
        "current_version": 1,
    }
    row.update(overrides)
    return row


@patch("app.marketplace.publish.write_audit_event")
@patch("app.marketplace.publish.assert_org_can_publish_publicly")
@patch("app.marketplace.publish.validate_asset_payload")
@patch("app.marketplace.publish._fetch_asset")
def test_submit_asset_for_public_review(mock_fetch, mock_validate, _mock_onboard, mock_audit):
    mock_fetch.return_value = _asset_row()
    mock_validate.return_value = {
        "config": {},
        "required_connectors": [],
        "install_variables": [],
    }
    assets = MagicMock()
    assets.update.return_value = assets
    assets.eq.return_value = assets
    assets.execute.return_value = MagicMock(data=[{"id": "asset-1"}])
    client = MagicMock()
    client.table.return_value = assets
    mock_fetch.side_effect = [_asset_row(), _asset_row(status="pending_review", review_scope="public")]

    result = submit_asset_for_public_review(
        client,
        ORG_ID,
        "public-agent",
        actor_id="admin-1",
    )
    assert result["submitted"] is True
    mock_audit.assert_called_once()


@patch("app.marketplace.publish._serialize_asset")
def test_list_public_review_queue(mock_serialize):
    assets = MagicMock()
    assets.select.return_value = assets
    assets.eq.return_value = assets
    assets.order.return_value = assets
    assets.range.return_value = assets
    assets.execute.return_value = MagicMock(
        data=[_asset_row(status="pending_review", review_scope="public")],
        count=1,
    )
    client = MagicMock()
    client.table.return_value = assets
    mock_serialize.return_value = {"slug": "public-agent"}

    result = list_public_review_queue(client, limit=10)
    assert result["total"] == 1
    assert len(result["assets"]) == 1


@patch("app.marketplace.publish._fetch_asset")
def test_approve_asset_for_public_publish_requires_scope(mock_fetch):
    mock_fetch.return_value = _asset_row(status="pending_review", review_scope="internal")
    client = MagicMock()
    with pytest.raises(MarketplacePublishError):
        approve_asset_for_public_publish(client, "public-agent", actor_id="platform-1")
