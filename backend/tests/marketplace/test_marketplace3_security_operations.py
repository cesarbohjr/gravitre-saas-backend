from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.security_operations import (
    SECURITY_OPERATIONS_PLAY_KEYS,
    build_security_operations_outcome_pack_config,
)
from app.marketplace.schemas import OutcomePackAssetConfig
from app.plays.catalog import get_platform_play


def test_security_operations_blueprint_is_structurally_valid() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )

    assert config.marketplace_version == "3.0"
    assert len(config.plays) == 8
    assert tuple(play.key for play in config.plays) == SECURITY_OPERATIONS_PLAY_KEYS
    assert len(config.agents) == 3
    assert len(config.outcome_contract.kpis) == len(config.dashboard.metrics)


def test_security_operations_plays_are_registered_in_canonical_catalog() -> None:
    for key in SECURITY_OPERATIONS_PLAY_KEYS:
        play = get_platform_play(key)
        assert play is not None
        assert play.objective.strip()
        assert play.outcome_metrics


def test_security_operations_blueprint_is_not_publish_ready_without_runtime_and_skills() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )

    report = certify_outcome_pack(config)
    codes = {finding.code for finding in report.findings}

    assert report.level == "compatible"
    assert report.publish_ready is False
    assert "RUNTIME_PROFILE_MISSING" in codes
    assert "SKILL_REQUIREMENTS_UNRESOLVED" in codes
    assert set(report.unresolved_skill_requirements) == {
        "security-alert-correlation",
        "vulnerability-risk-prioritization",
        "identity-compromise-analysis",
        "incident-response-reasoning",
    }


def test_security_operations_containment_requires_approval_and_verification() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )
    containment = next(
        play for play in config.plays if play.key == "containment-coordinator"
    )

    assert containment.approvals == [{"when": "external_write", "required": True}]
    assert containment.verification["mode"] == "source_of_record"
    assert containment.verification["provider_acceptance_is_terminal"] is False


def test_security_operations_dashboard_covers_every_outcome_kpi() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )

    outcome_kpis = {kpi.key for kpi in config.outcome_contract.kpis}
    dashboard_kpis = {metric.kpi_key for metric in config.dashboard.metrics}
    assert dashboard_kpis == outcome_kpis
