"""MKT-4: Starter marketplace catalog validation."""
from __future__ import annotations

import pytest

from app.marketplace.schemas import validate_asset_payload
from app.marketplace.seed_catalog import LEGACY_PACK_SLUG_MAP, catalog_assets_by_slug, list_catalog_assets


def test_catalog_asset_counts():
    assets = list_catalog_assets()
    by_type: dict[str, int] = {}
    for asset in assets:
        by_type[asset.asset_type] = by_type.get(asset.asset_type, 0) + 1
    assert by_type["ai_agent"] == 8
    assert by_type["workflow"] == 8
    assert by_type["knowledge_pack"] == 6
    assert by_type["department_pack"] == 5
    assert len(assets) == 27


@pytest.mark.parametrize("asset_slug", sorted(catalog_assets_by_slug()))
def test_catalog_asset_validates(asset_slug: str):
    asset = catalog_assets_by_slug()[asset_slug]
    validated = validate_asset_payload(
        asset_type=asset.asset_type,
        config=asset.config,
        install_variables=asset.install_variables,
        required_connectors=asset.required_connectors,
        publish=True,
    )
    assert validated["config"]


def test_department_pack_children_exist():
    by_slug = catalog_assets_by_slug()
    for asset in list_catalog_assets():
        if asset.asset_type != "department_pack":
            continue
        for child_slug in asset.pack_children:
            assert child_slug in by_slug, f"{asset.slug} missing child {child_slug}"


def test_legacy_pack_slug_map_targets_catalog():
    by_slug = catalog_assets_by_slug()
    for legacy_id, mapped_slug in LEGACY_PACK_SLUG_MAP.items():
        assert mapped_slug in by_slug, f"legacy {legacy_id} maps to missing slug {mapped_slug}"
