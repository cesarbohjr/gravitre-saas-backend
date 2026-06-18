"""MKT-AUDIT-9.1: Org-owned marketplace asset CRUD."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.crud import (
    MarketplaceCrudError,
    archive_org_asset,
    create_org_asset,
    update_org_asset,
)
from app.workflows.constants import SCHEMA_VERSION

ORG_ID = "org-11111111-1111-1111-1111-111111111111"
PUBLISHER_ID = "pub-org-1"


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])
    return mock


def _draft_agent_asset(**overrides) -> dict:
    base = {
        "id": "asset-1",
        "slug": "custom-agent",
        "title": "Custom Agent",
        "description": "Draft agent",
        "asset_type": "ai_agent",
        "category": "ai_agent",
        "department": "Marketing",
        "tags": [],
        "visibility": "private",
        "status": "draft",
        "pricing_type": "free",
        "price_cents": 0,
        "currency": "usd",
        "config": {
            "name": "Custom Agent",
            "purpose": "Analyze campaigns",
            "role": "Analyst",
            "department": "Marketing",
            "systems": [],
        },
        "required_connectors": [],
        "required_permissions": [],
        "install_variables": [],
        "publisher_id": PUBLISHER_ID,
        "org_id": ORG_ID,
        "current_version": 1,
    }
    base.update(overrides)
    return base


@patch("app.marketplace.crud.write_audit_event")
@patch("app.marketplace.crud.resolve_org_publisher_id", return_value=PUBLISHER_ID)
def test_create_asset_as_draft(mock_publisher, mock_audit):
    assets = _table([])
    versions = _table([{"id": "ver-1"}])
    assets.insert.return_value = assets
    assets.execute.side_effect = [
        MagicMock(data=[]),
        MagicMock(data=[_draft_agent_asset()]),
    ]

    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else versions

    result = create_org_asset(
        client,
        ORG_ID,
        actor_id="user-1",
        slug="custom-agent",
        title="Custom Agent",
        asset_type="ai_agent",
        config=_draft_agent_asset()["config"],
    )
    assert result["created"] is True
    assert result["asset"]["status"] == "draft"
    assert result["asset"]["visibility"] == "private"
    mock_audit.assert_called_once()


@patch("app.marketplace.crud.write_audit_event")
def test_create_asset_validates_schema(mock_audit):
    assets = _table([])
    client = MagicMock()
    client.table.return_value = assets

    with pytest.raises(MarketplaceCrudError) as exc:
        create_org_asset(
            client,
            ORG_ID,
            actor_id="user-1",
            slug="bad-agent",
            title="Bad Agent",
            asset_type="ai_agent",
            config={"name": ""},
        )
    assert exc.value.code == "VALIDATION_ERROR"


@patch("app.marketplace.crud.write_audit_event")
@patch("app.marketplace.crud._fetch_asset")
def test_update_only_allowed_in_draft_or_pending(mock_fetch, mock_audit):
    updated = _draft_agent_asset(title="Updated")
    mock_fetch.side_effect = [_draft_agent_asset(status="draft"), updated]
    assets = _table()
    assets.update.return_value = assets
    client = MagicMock()
    client.table.return_value = assets

    result = update_org_asset(
        client,
        ORG_ID,
        "asset-1",
        actor_id="user-1",
        patch={"title": "Updated"},
    )
    assert result["updated"] is True
    assert result["asset"]["title"] == "Updated"


@patch("app.marketplace.crud._fetch_asset")
def test_update_rejected_for_published_asset(mock_fetch):
    mock_fetch.return_value = _draft_agent_asset(status="published", visibility="internal")
    client = MagicMock()
    with pytest.raises(MarketplaceCrudError) as exc:
        update_org_asset(client, ORG_ID, "asset-1", actor_id="user-1", patch={"title": "Nope"})
    assert exc.value.code == "FORBIDDEN"


@patch("app.marketplace.crud.write_audit_event")
@patch("app.marketplace.crud._fetch_asset")
def test_archive_is_soft_delete(mock_fetch, mock_audit):
    mock_fetch.side_effect = [
        _draft_agent_asset(status="draft"),
        _draft_agent_asset(status="archived"),
    ]
    assets = _table()
    assets.update.return_value = assets
    assets.execute.return_value = MagicMock(data=[])
    client = MagicMock()
    client.table.return_value = assets

    result = archive_org_asset(client, ORG_ID, "asset-1", actor_id="user-1")
    assert result["archived"] is True
    assert result["asset"]["status"] == "archived"


def test_archived_asset_still_fetchable_for_install_lookup():
    from app.marketplace.crud import fetch_archived_asset_for_install_lookup

    asset_id = "44444444-4444-4444-4444-444444444444"
    archived = _draft_agent_asset(id=asset_id, status="archived")
    assets = _table([archived])
    client = MagicMock()
    client.table.return_value = assets

    row = fetch_archived_asset_for_install_lookup(client, asset_id)
    assert row is not None
    assert row["status"] == "archived"


def test_create_rejects_invalid_slug():
    assets = _table([])
    client = MagicMock()
    client.table.return_value = assets
    with pytest.raises(MarketplaceCrudError) as exc:
        create_org_asset(
            client,
            ORG_ID,
            actor_id="user-1",
            slug="!!!",
            title="Title",
            asset_type="workflow",
            config={
                "schema_version": SCHEMA_VERSION,
                "name": "Flow",
                "description": "desc",
                "steps": [{"id": "s1", "name": "Step", "type": "noop"}],
            },
        )
    assert exc.value.code == "VALIDATION_ERROR"
