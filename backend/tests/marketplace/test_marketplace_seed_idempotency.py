"""MKT-AUDIT-4.5: Seed script idempotency."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.marketplace.seed_catalog import list_catalog_assets
from app.marketplace.seed_service import upsert_catalog_asset


@patch("app.marketplace.seed_service.fetch_publisher_id", return_value="pub-1")
def test_rerunning_seed_does_not_duplicate_assets(mock_publisher):
    asset = list_catalog_assets()[0]
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.upsert.return_value = table
    table.execute.side_effect = [
        MagicMock(data=[]),
        MagicMock(data=[{"id": "asset-1", "current_version": 1}]),
        MagicMock(data=[]),
        MagicMock(data=[{"id": "asset-1", "current_version": 1}]),
        MagicMock(data=[{"id": "asset-1", "current_version": 1}]),
        MagicMock(data=[{"id": "asset-1", "current_version": 1}]),
        MagicMock(data=[]),
    ]
    client = MagicMock()
    client.table.return_value = table

    upsert_catalog_asset(client, "pub-1", asset)
    upsert_catalog_asset(client, "pub-1", asset)

    assert table.insert.call_count == 1
    assert table.update.call_count == 1


def test_internal_draft_seed_keeps_parent_unpublished_and_versions_timestamped():
    from datetime import datetime
    from types import SimpleNamespace

    asset = next(a for a in list_catalog_assets() if a.slug == "msp-service-desk-3")
    assets = MagicMock()
    assets.select.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(data=[])
    assets.insert.return_value.execute.return_value = SimpleNamespace(data=[{"id": "asset-1"}])
    versions = MagicMock()
    versions.upsert.return_value.execute.return_value = SimpleNamespace(data=[])
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else versions

    upsert_catalog_asset(client, "pub-1", asset)

    parent = assets.insert.call_args.args[0]
    version = versions.upsert.call_args.args[0]
    assert parent["status"] == "draft"
    assert parent["published_at"] is None
    assert datetime.fromisoformat(version["published_at"]).tzinfo is not None
