"""Offline regression contracts for the Agency Agents staging catalog."""
import json
from pathlib import Path

import pytest

from app.marketplace.agency_agents_catalog import (
    load_agency_inventory, preview_marketplace_candidates,
    approved_marketplace_candidates,
    map_marketplace_targets,
)


def test_complete_division_inventory():
    data = load_agency_inventory()
    assert len(data["divisions"]) == 18
    assert len(data["agents"]) == 283
    assert {a["division"] for a in data["agents"]} == set(data["divisions"])
    assert all(a["publication_status"] == "draft_unapproved" for a in data["agents"])


def test_marketplace_previews_are_not_published():
    data = load_agency_inventory()
    previews = preview_marketplace_candidates()
    assert len(previews) == sum(a["proposed_disposition"] == "marketplace_agent" for a in data["agents"])
    assert all(a.config["config"]["publication_status"] == "draft_unapproved" for a in previews)
    assert all(a.config["config"]["source_revision"] == data["source_commit"] for a in previews)


def test_previews_use_install_schema_without_granting_tool_access():
    from app.marketplace.schemas import AgentAssetConfig
    from app.marketplace.seed_catalog import list_catalog_assets

    published_slugs = {a.slug for a in list_catalog_assets()}
    for asset in preview_marketplace_candidates():
        config = AgentAssetConfig.model_validate(asset.config)
        assert config.name == asset.title
        assert config.department == asset.department
        assert config.systems == []
        assert config.capabilities == []
        assert config.persona_key is None  # Never invent an executable persona.
        assert asset.required_connectors == []
        assert asset.slug not in published_slugs
        assert "system_prompt" not in config.config


def test_every_division_maps_to_explicit_review_targets():
    from app.capabilities.agent_manifest import resolve_agent_manifest
    from app.marketplace.seed_catalog import list_catalog_assets

    data = load_agency_inventory()
    catalog = {a.slug: a for a in list_catalog_assets()}
    mappings = map_marketplace_targets()
    assert {a["slug"] for a in mappings} == {a["slug"] for a in data["agents"]}
    for row in mappings:
        assert row["live_catalog_review_required"]
        if not row["product_approval_required"]:
            assert row["approval_scope"] == "existing_agent_enrichment"
        assert row["comparison_scope"] == "repository_seed_catalog_only"
        assert not row["catalog_slug_collision"]
        if row["candidate_pack_slug"]:
            assert catalog[row["candidate_pack_slug"]].asset_type == "department_pack"
        if row["manifest_role"]:
            assert resolve_agent_manifest(row["manifest_role"]) is not None
    seo = next(a for a in mappings if a["slug"] == "agency-marketing-seo-specialist")
    assert seo["candidate_agent_slug"] == "seo-analyst"
    assert seo["conflict_disposition"] == "review_enrichment"


def test_profiles_have_pinned_source_audit():
    import re

    data = load_agency_inventory()
    audit = data["source_audit"]
    assert audit["revision"] == data["source_commit"]
    assert audit["profile_count"] == len(data["agents"])
    assert audit["license"] == "MIT"
    assert audit["runtime_text_imported"] is False
    assert all(re.fullmatch(r"[a-f0-9]{64}", a["source_sha256"]) for a in data["agents"])


def test_initial_orgscript_exclusion_is_preserved():
    excluded = "agency-engineering-orgscript-engineer"
    row = next(a for a in map_marketplace_targets() if a["slug"] == excluded)
    assert row["proposed_disposition"] == "exclude"
    assert row["conflict_disposition"] == "exclude_pending_review"
    assert row["manifest_role"] is None
    assert row["candidate_agent_slug"] is None
    assert excluded not in {a.slug for a in preview_marketplace_candidates()}


def test_approval_is_fail_closed():
    approved = approved_marketplace_candidates()
    assert {asset.slug for asset in approved} == {"content-writer", "seo-analyst", "sdr-coach", "ticket-triage"}
    assert not any(asset.slug.startswith("agency-") for asset in approved)


def test_review_preview_cannot_be_published_by_seed_service():
    from unittest.mock import MagicMock
    from app.marketplace.seed_service import upsert_catalog_asset

    client = MagicMock()
    for preview in preview_marketplace_candidates():
        with pytest.raises(PermissionError, match="product approval"):
            upsert_catalog_asset(client, "publisher", preview)
    client.table.assert_not_called()


@pytest.mark.parametrize("mutation", [
    lambda x: x["agents"][0].update(slug=x["agents"][1]["slug"]),
    lambda x: x["agents"][0].update(publication_status="published"),
    lambda x: x["agents"][0].update(source_url="https://evil.example/agent.md"),
    lambda x: x["agents"][0].update(division="not-a-division"),
    lambda x: x.update(source_commit="main"),
    lambda x: x.update(source_commit="z" * 40),
    lambda x: x.update(source_repo="attacker/agency-agents"),
    lambda x: x["agents"][0].update(source_url=x["agents"][0]["source_url"] + "?redirect=evil"),
    lambda x: x["agents"][0].update(source_path="engineering/../../evil.md"),
    lambda x: x["agents"][0].update(source_sha256="unverified"),
    lambda x: x["agents"][0].update(source_license="unknown"),
])
def test_invalid_catalog_fails_closed(tmp_path: Path, mutation):
    data = load_agency_inventory()
    mutation(data)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_agency_inventory(path)
