"""MKT-AUDIT-9.2: Internal publish workflow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.publish import (
    MarketplacePublishError,
    approve_asset_for_internal_publish,
    reject_asset_review,
    submit_asset_for_review,
)
from app.workflows.constants import SCHEMA_VERSION

ORG_ID = "org-11111111-1111-1111-1111-111111111111"


def _draft_asset(**overrides) -> dict:
    base = {
        "id": "asset-1",
        "slug": "custom-agent",
        "title": "Custom Agent",
        "asset_type": "ai_agent",
        "status": "draft",
        "visibility": "private",
        "org_id": ORG_ID,
        "publisher_id": "pub-1",
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
        "current_version": 1,
    }
    base.update(overrides)
    return base


def _table() -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.execute.return_value = MagicMock(data=[])
    return mock


@patch("app.marketplace.publish.write_audit_event")
@patch("app.marketplace.publish._fetch_asset")
def test_submit_for_review_transitions_status(mock_fetch, mock_audit):
    mock_fetch.side_effect = [
        _draft_asset(),
        _draft_asset(status="pending_review"),
    ]
    assets = _table()
    client = MagicMock()
    client.table.return_value = assets

    result = submit_asset_for_review(client, ORG_ID, "asset-1", actor_id="user-1")
    assert result["submitted"] is True
    assert result["asset"]["status"] == "pending_review"


@patch("app.marketplace.publish._fetch_asset")
def test_submit_applies_stricter_validation(mock_fetch):
    mock_fetch.return_value = _draft_asset(
        config={
            "name": "Custom Agent",
            "purpose": "",
            "role": "Analyst",
            "department": "Marketing",
            "systems": [],
        }
    )
    client = MagicMock()
    with pytest.raises(MarketplacePublishError) as exc:
        submit_asset_for_review(client, ORG_ID, "asset-1", actor_id="user-1")
    assert exc.value.code == "VALIDATION_ERROR"


@patch("app.marketplace.publish.write_audit_event")
@patch("app.marketplace.publish._fetch_asset")
def test_approve_sets_internal_visibility(mock_fetch, mock_audit):
    mock_fetch.side_effect = [
        _draft_asset(status="pending_review"),
        _draft_asset(status="published", visibility="internal", current_version=2),
    ]
    assets = _table()
    versions = _table()
    client = MagicMock()

    def table(name):
        if name == "marketplace_asset_versions":
            return versions
        return assets

    client.table.side_effect = table

    result = approve_asset_for_internal_publish(client, ORG_ID, "asset-1", actor_id="admin-1")
    assert result["approved"] is True
    assert result["asset"]["visibility"] == "internal"
    assert result["asset"]["status"] == "published"


@patch("app.marketplace.publish.write_audit_event")
@patch("app.marketplace.publish._fetch_asset")
def test_reject_returns_to_draft_with_reason(mock_fetch, mock_audit):
    mock_fetch.side_effect = [
        _draft_asset(status="pending_review"),
        _draft_asset(status="draft"),
    ]
    client = MagicMock()
    client.table.return_value = _table()

    result = reject_asset_review(
        client,
        ORG_ID,
        "asset-1",
        actor_id="admin-1",
        reason="Needs clearer business outcome",
    )
    assert result["rejected"] is True
    assert "business outcome" in result["reason"]
