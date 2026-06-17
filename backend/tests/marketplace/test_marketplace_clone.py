"""Tests for marketplace asset clone (MKT-7.2)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.clone import MarketplaceCloneError, clone_asset


SOURCE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "slug": "marketing-analyst",
    "title": "Marketing Analyst",
    "description": "Starter agent",
    "asset_type": "ai_agent",
    "category": "ai_agent",
    "department": "Marketing",
    "tags": ["marketing"],
    "visibility": "public",
    "status": "published",
    "pricing_type": "free",
    "price_cents": 0,
    "currency": "usd",
    "config": {"name": "Marketing Analyst"},
    "required_connectors": [],
    "required_permissions": [],
    "install_variables": [],
    "publisher_id": "pub-1",
    "clone_count": 2,
}


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])
    return mock


@patch("app.marketplace.clone.write_audit_event")
@patch("app.marketplace.clone.resolve_browsable_asset", return_value=SOURCE)
def test_clone_asset_creates_private_draft(mock_resolve, mock_audit):
    slug_checks = _table([])
    slug_checks.execute.side_effect = [
        MagicMock(data=[]),
        MagicMock(data=[]),
    ]
    assets = _table()
    assets.insert.return_value = assets
    assets.update.return_value = assets
    assets.execute.side_effect = [
        MagicMock(data=[]),
        MagicMock(
            data=[
                {
                    "id": "clone-1",
                    "slug": "marketing-analyst-copy",
                    "title": "Marketing Analyst (Copy)",
                    "asset_type": "ai_agent",
                    "visibility": "private",
                    "status": "draft",
                    "org_id": "org-1",
                    "cloned_from_asset_id": SOURCE["id"],
                }
            ]
        ),
        MagicMock(data=[]),
    ]

    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else _table([])

    result = clone_asset(client, "org-1", "marketing-analyst", actor_id="user-1")
    assert result["cloned"] is True
    assert result["asset"]["status"] == "draft"
    assert result["asset"]["visibility"] == "private"
    assert result["asset"]["slug"] == "marketing-analyst-copy"
    mock_audit.assert_called_once()
    update_call = assets.update.call_args
    assert update_call is not None


@patch("app.marketplace.clone.resolve_browsable_asset")
def test_clone_asset_not_found(mock_resolve):
    from app.marketplace.browse import MarketplaceBrowseError

    mock_resolve.side_effect = MarketplaceBrowseError("not found", code="NOT_FOUND")
    client = MagicMock()
    with pytest.raises(MarketplaceCloneError) as exc:
        clone_asset(client, "org-1", "missing", actor_id="user-1")
    assert exc.value.code == "NOT_FOUND"
