from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.security_operations import (
    SECURITY_OPERATIONS_PLAY_KEYS,
    build_security_operations_outcome_pack_config,
    build_security_operations_skill_package_config,
    security_operations_marketplace3_assets,
)
from app.marketplace.schemas import OutcomePackAssetConfig, parse_asset_config
from app.plays.catalog import get_platform_play


def test_security_operations_flagship_is_valid_marketplace3_outcome_pack() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )
    assert config.marketplace_version == "3.0"
    assert len(config.plays) == 9
    assert {play.key for play in config.plays} == set(SECURITY_OPERATIONS_PLAY_KEYS)
    assert len(config.agents) == 5
    assert len(config.outcome_contract.kpis) >= 10
    assert {
        metric.kpi_key for metric in config.dashboard.metrics
    } == {kpi.key for kpi in config.outcome_contract.kpis}
    assert config.runtime_profiles[0].provider == "freshservice"
    assert config.runtime_profiles[0].status == "tested"
    assert config.connector_alternatives[0] == ["freshservice"]

    report = certify_outcome_pack(config)
    assert report.level == "governed"
    assert report.publish_ready is False


def test_security_operations_plays_are_canonical_and_measurable() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )
    for play in config.plays:
        canonical = get_platform_play(play.key)
        assert canonical is not None, play.key
        assert canonical.objective
        assert canonical.outcome_metrics
        assert play.outcome_events
        assert play.kpi_keys
        assert play.verification.provider_acceptance_is_terminal is False


def test_security_operations_catalog_contains_complete_internal_bundle() -> None:
    assets = security_operations_marketplace3_assets()
    types = [asset.asset_type for asset in assets]
    slugs = {asset.slug for asset in assets}
    outcome = next(asset for asset in assets if asset.asset_type == "outcome_pack")

    assert types.count("ai_agent") == 5
    assert types.count("play") == 9
    assert types.count("capability_package") == 1
    assert types.count("knowledge_pack") == 1
    assert types.count("dataset_pack") == 1
    assert types.count("dashboard_pack") == 1
    assert types.count("outcome_pack") == 1
    assert outcome.status == "draft"
    assert outcome.visibility == "internal"
    assert "production-verified" not in outcome.tags
    assert "outcome-verified" not in outcome.tags
    assert all(asset.status == "draft" for asset in assets)
    assert all(asset.visibility == "internal" for asset in assets)
    assert len(outcome.pack_children) == 18
    assert set(outcome.pack_children) <= slugs
    assert outcome.price_cents == 0
    parse_asset_config("outcome_pack", outcome.config, publish=False)


def test_security_operations_skill_package_reuses_reviewed_git_pinned_bundle() -> None:
    parsed = parse_asset_config(
        "capability_package",
        build_security_operations_skill_package_config(),
        publish=True,
    )
    assert parsed.provenance_mode == "git_pinned"
    assert parsed.package_format == "gravitre"
    assert parsed.risk_level == "low"


def test_security_operations_containment_and_comms_stay_approval_governed() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )
    by_key = {play.key: play for play in config.plays}
    containment = by_key["containment-readiness-review"]
    communications = by_key["incident-communications-brief"]

    assert containment.approvals
    assert containment.approvals[0]["required"] is True
    assert communications.approvals
    assert communications.approvals[0]["required"] is True


def test_security_operations_dataset_models_operating_evidence() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )
    entities = {entity.name for entity in config.dataset.entities}
    assert {
        "security_cases",
        "security_assets",
        "identity_risk",
        "vulnerabilities",
        "remediation_items",
        "incident_timeline",
        "verified_outcomes",
    } <= entities
