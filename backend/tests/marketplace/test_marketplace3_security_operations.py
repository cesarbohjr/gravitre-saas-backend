from app.marketplace.marketplace3.security_operations import (
    SECURITY_OPERATIONS_PLAY_KEYS,
    build_security_operations_outcome_pack_config,
)
from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.schemas import OutcomePackAssetConfig


def test_security_operations_blueprint_is_valid_marketplace3_outcome_pack() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )
    assert config.marketplace_version == "3.0"
    assert len(config.plays) == 8
    assert {play.key for play in config.plays} == set(SECURITY_OPERATIONS_PLAY_KEYS)
    assert len(config.agents) == 4
    assert len(config.outcome_contract.kpis) >= 15
    assert {metric.kpi_key for metric in config.dashboard.metrics} == {
        kpi.key for kpi in config.outcome_contract.kpis
    }


def test_security_operations_certifies_governed_but_not_publish_ready() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )
    report = certify_outcome_pack(config)
    codes = {finding.code for finding in report.findings}

    assert report.level == "governed"
    assert report.publish_ready is False
    assert "RUNTIME_ACTION_NOT_REGISTERED" not in codes
    assert "ACTION_SPEC_MISSING" not in codes
    assert "SKILL_REQUIREMENTS_UNRESOLVED" not in codes
    assert report.unresolved_skill_requirements == []


def test_security_operations_blueprint_is_not_seeded_as_published_asset() -> None:
    payload = build_security_operations_outcome_pack_config()
    assert "status" not in payload
    assert "visibility" not in payload


def test_existing_published_security_pack_play_keys_remain_installable() -> None:
    from app.marketplace.marketplace3.department_portfolio import PACK_SPECS
    from app.plays.catalog import get_platform_play

    legacy_keys = {row[0] for row in PACK_SPECS["security-operations-3"]["plays"]}
    missing = sorted(key for key in legacy_keys if get_platform_play(key) is None)
    assert missing == []
