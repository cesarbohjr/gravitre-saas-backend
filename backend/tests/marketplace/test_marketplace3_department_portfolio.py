from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.capabilities.provenance import bundle_digest, inert_snapshot_digest
from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.department_portfolio import (
    PACK_SPECS,
    SKILL_COMMIT,
    SKILL_PACKS,
    build_department_outcome_pack_config,
    department_portfolio_marketplace3_assets,
)
from app.marketplace.schemas import MarketplaceValidationError, OutcomePackAssetConfig, parse_asset_config
from app.plays.catalog import get_platform_play


@pytest.mark.parametrize("slug", sorted(PACK_SPECS))
def test_department_pack_is_governed_but_not_production_verified_without_live_evidence(slug: str) -> None:
    raw = build_department_outcome_pack_config(slug)
    config = OutcomePackAssetConfig.model_validate(raw)

    assert config.marketplace_version == "3.0"
    assert len(config.plays) >= 8
    assert len(config.agents) >= 2
    assert config.skill_requirements
    assert config.runtime_profiles
    assert {
        metric.kpi_key for metric in config.dashboard.metrics
    } == {kpi.key for kpi in config.outcome_contract.kpis}

    report = certify_outcome_pack(config)
    assert report.publish_ready is False, [finding.as_dict() for finding in report.findings]
    assert report.level == "governed"
    assert report.unresolved_skill_requirements == []
    with pytest.raises(MarketplaceValidationError) as exc:
        parse_asset_config("outcome_pack", raw, publish=True)
    assert any("certification" in error for error in exc.value.errors)


@pytest.mark.parametrize("slug", sorted(PACK_SPECS))
def test_department_plays_are_canonical_and_measurable(slug: str) -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_department_outcome_pack_config(slug)
    )
    for play in config.plays:
        canonical = get_platform_play(play.key)
        assert canonical is not None, play.key
        assert canonical.objective
        assert canonical.outcome_metrics
        assert play.outcome_events
        assert play.kpi_keys


def test_department_portfolio_catalog_has_complete_components() -> None:
    assets = department_portfolio_marketplace3_assets()
    by_slug = {asset.slug: asset for asset in assets}

    assert len(by_slug) == len(assets)
    assert sum(asset.asset_type == "outcome_pack" for asset in assets) == len(PACK_SPECS)
    assert sum(asset.asset_type == "capability_package" for asset in assets) == len(PACK_SPECS)

    for slug, spec in PACK_SPECS.items():
        outcome = by_slug[slug]
        assert outcome.asset_type == "outcome_pack"
        assert outcome.pack_tier == 3
        assert outcome.status == "draft"
        assert outcome.visibility == "internal"
        assert "production-verified" not in outcome.tags
        config = OutcomePackAssetConfig.model_validate(outcome.config or {})
        assert len(outcome.pack_children) == len(config.agents) + len(config.plays) + 4
        assert set(outcome.pack_children) <= set(by_slug)
        assert spec["skill_package"] in outcome.pack_children
        related = [asset for asset in assets if asset.slug == slug or asset.slug in outcome.pack_children]
        assert related
        assert all(asset.status == "draft" for asset in related)
        assert all(asset.visibility == "internal" for asset in related)


@pytest.mark.parametrize("slug", sorted(SKILL_PACKS))
def test_department_skill_package_matches_git_pinned_snapshot(slug: str) -> None:
    assets = department_portfolio_marketplace3_assets()
    asset = next(item for item in assets if item.slug == slug)
    parsed = parse_asset_config("capability_package", asset.config, publish=True)

    assert parsed.provenance_mode == "git_pinned"
    assert parsed.commit_sha == SKILL_COMMIT
    base = Path(__file__).resolve().parents[3] / "capability_packages" / slug
    files = {
        "SKILL.md": (base / "SKILL.md").read_text(),
        "manifest.json": (base / "manifest.json").read_text(),
    }
    assert bundle_digest(files) == asset.config["content_digest"]
    assert json.loads(files["manifest.json"]) == asset.config["manifest"]
    assert inert_snapshot_digest(
        manifest=asset.config["manifest"],
        resources=asset.config["resources"],
    ) == asset.config["snapshot_digest"]


def test_portfolio_contains_at_least_56_new_plays() -> None:
    assets = department_portfolio_marketplace3_assets()
    plays = [asset for asset in assets if asset.asset_type == "play"]
    assert len(plays) >= 56
    assert len({asset.slug for asset in plays}) == len(plays)


def test_each_department_pack_includes_eighth_high_value_play() -> None:
    expected = {
        "security-operations-3": "security-posture-watch",
        "revenue-operations-3": "post-meeting-follow-up-review",
        "customer-success-support-3": "voice-of-customer-watch",
        "finance-operations-3": "revenue-leak-hunter",
        "marketing-operations-3": "lifecycle-conversion-review",
        "people-it-operations-3": "service-request-bottleneck-review",
        "executive-command-center-3": "operational-anomaly-watch",
    }
    for slug, play_key in expected.items():
        config = OutcomePackAssetConfig.model_validate(
            build_department_outcome_pack_config(slug)
        )
        assert len(config.plays) >= 8
        assert play_key in {play.key for play in config.plays}
        play = next(play for play in config.plays if play.key == play_key)
        assert play.outcome_events
        assert play.kpi_keys
        assert get_platform_play(play_key) is not None
