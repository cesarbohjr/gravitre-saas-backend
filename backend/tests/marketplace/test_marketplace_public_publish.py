"""MKT-AUDIT-11.2: Gravitre public review queue."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.publish import (
    MarketplacePublishError,
    approve_asset_for_public_publish,
    get_public_review_asset_detail,
    list_public_review_queue,
    reject_asset_public_review,
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


def _table():
    table = MagicMock()
    table.update.return_value = table
    table.eq.return_value = table
    table.execute.return_value = MagicMock(data=[{"id": "asset-1"}])
    table.insert.return_value = table
    return table


@patch("app.marketplace.publish.validate_asset_payload")
@patch("app.marketplace.publish.write_audit_event")
@patch("app.marketplace.publish._fetch_asset")
def test_approve_asset_for_public_publish_snapshots_version(mock_fetch, mock_audit, mock_validate):
    mock_fetch.side_effect = [
        _asset_row(status="pending_review", review_scope="public"),
        _asset_row(status="published", visibility="public", review_scope="public", current_version=2),
    ]
    mock_validate.return_value = {
        "config": {"prompt": "hello"},
        "required_connectors": [],
        "install_variables": [],
    }
    assets = _table()
    versions = _table()
    client = MagicMock()

    def table(name):
        if name == "marketplace_asset_versions":
            return versions
        return assets

    client.table.side_effect = table

    result = approve_asset_for_public_publish(client, "public-agent", actor_id="platform-1")
    assert result["approved"] is True
    assert result["asset"]["visibility"] == "public"
    assert result["asset"]["status"] == "published"
    versions.insert.assert_called_once()
    insert_payload = versions.insert.call_args.args[0]
    assert insert_payload["version_number"] == 2
    assert insert_payload["change_summary"] == "Public catalog publish approval"


@patch("app.marketplace.publish.write_audit_event")
@patch("app.marketplace.publish._fetch_asset")
def test_reject_asset_public_review_returns_to_draft(mock_fetch, mock_audit):
    mock_fetch.side_effect = [
        _asset_row(status="pending_review", review_scope="public"),
        _asset_row(status="draft", review_scope="public"),
    ]
    client = MagicMock()
    client.table.return_value = _table()

    result = reject_asset_public_review(
        client,
        "public-agent",
        actor_id="platform-1",
        reason="Needs clearer business outcome",
    )
    assert result["rejected"] is True
    assert "business outcome" in result["reason"]


@patch("app.marketplace.publish._serialize_asset")
@patch("app.marketplace.publish._fetch_asset")
def test_get_public_review_asset_detail(mock_fetch, mock_serialize):
    mock_fetch.return_value = _asset_row(status="pending_review", review_scope="public", publisher_id="pub-1")
    mock_serialize.return_value = {"slug": "public-agent", "publisherId": "pub-1"}
    publishers = MagicMock()
    publishers.select.return_value = publishers
    publishers.eq.return_value = publishers
    publishers.limit.return_value = publishers
    publishers.execute.return_value = MagicMock(
        data=[{"display_name": "Acme Creators", "slug": "acme", "website_url": "https://acme.test", "verified": True}]
    )
    client = MagicMock()
    client.table.return_value = publishers

    result = get_public_review_asset_detail(client, "public-agent")
    assert result["asset"]["publisherDisplayName"] == "Acme Creators"
    assert result["asset"]["publisherVerified"] is True


@patch("app.marketplace.publish._fetch_asset")
def test_get_public_review_asset_detail_requires_public_pending(mock_fetch):
    mock_fetch.return_value = _asset_row(status="draft", review_scope="public")
    client = MagicMock()
    with pytest.raises(MarketplacePublishError):
        get_public_review_asset_detail(client, "public-agent")
