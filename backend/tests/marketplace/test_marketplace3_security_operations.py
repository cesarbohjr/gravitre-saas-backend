from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.certification_runner import fixture_checks
from app.marketplace.marketplace3.security_operations import (
    SECURITY_OPERATIONS_PLAY_KEYS,
    build_security_operations_outcome_pack_config,
)
from app.marketplace.schemas import OutcomePackAssetConfig
from app.plays.catalog import get_platform_play


def _config() -> OutcomePackAssetConfig:
    return OutcomePackAssetConfig.model_validate(
        build_security_operations_outcome_pack_config()
    )


def test_security_operations_flagship_is_structurally_complete() -> None:
    config = _config()

    assert config.marketplace_version == "3.0"
    assert tuple(play.key for play in config.plays) == SECURITY_OPERATIONS_PLAY_KEYS
    assert len(config.plays) == 8
    assert len(config.agents) == 6
    assert len(config.knowledge) == 5
    assert len(config.dataset.entities) >= 6
    assert len(config.outcome_contract.kpis) == 11
    assert {metric.kpi_key for metric in config.dashboard.metrics} == {
        kpi.key for kpi in config.outcome_contract.kpis
    }


def test_security_operations_plays_are_canonical_and_measurable() -> None:
    config = _config()

    for play in config.plays:
        canonical = get_platform_play(play.key)
        assert canonical is not None, play.key
        assert canonical.objective.strip()
        assert canonical.outcome_metrics
        assert play.outcome_events
        assert play.kpi_keys


def test_security_operations_fixture_contracts_pass() -> None:
    config = _config()
    failed = [check for check in fixture_checks(config) if not check.passed]
    assert failed == [], [check.as_dict() for check in failed]


def test_security_operations_is_governed_not_production_verified() -> None:
    config = _config()
    report = certify_outcome_pack(config)

    assert report.level == "governed"
    assert report.publish_ready is False
    assert report.unresolved_skill_requirements == []
    assert config.runtime_profiles[0].provider == "freshservice"
    assert config.runtime_profiles[0].status == "tested"
    assert set(config.runtime_profiles[0].actions) == {
        "freshservice.tickets.list",
        "freshservice.tickets.get",
        "freshservice.tickets.activities",
    }


def test_security_operations_containment_is_planning_only_until_write_contract_exists() -> None:
    config = _config()
    containment = next(
        play for play in config.plays if play.key == "containment-coordinator"
    )

    assert containment.approvals == [
        {"when": "external_containment_write", "required": True}
    ]
    assert containment.verification["mode"] == "source_of_record"
    assert containment.verification["provider_acceptance_is_terminal"] is False
    assert all(
        step.get("type") != "invoke_tool"
        or str((step.get("config") or {}).get("action", "")).startswith("freshservice.")
        for step in containment.workflow_steps
    )


def test_security_operations_does_not_claim_optional_security_connectors_as_runtime_profiles() -> None:
    config = _config()
    runtime_providers = {profile.provider for profile in config.runtime_profiles}

    assert runtime_providers == {"freshservice"}
    optional = {
        connector
        for group in config.connector_alternatives[1:]
        for connector in group
    }
    assert {"huntress", "sentinelone", "crowdstrike", "connectsecure"} <= optional
    assert optional.isdisjoint(runtime_providers)


def test_security_operations_declares_measurable_outcomes_for_all_plays() -> None:
    config = _config()
    declared = set(config.outcome_contract.outcome_events)
    play_events = {event for play in config.plays for event in play.outcome_events}

    assert play_events == declared
    assert "remediation_verification_reviewed" in declared
    assert "post_incident_review_completed" in declared
