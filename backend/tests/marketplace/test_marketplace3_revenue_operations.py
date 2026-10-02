from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.certification_runner import fixture_checks
from app.marketplace.marketplace3.department_portfolio import department_portfolio_marketplace3_assets
from app.marketplace.marketplace3.revenue_operations import (
    REVENUE_OPERATIONS_PLAY_KEYS,
    build_revenue_operations_outcome_pack_config,
)
from app.marketplace.schemas import OutcomePackAssetConfig


def _config() -> OutcomePackAssetConfig:
    return OutcomePackAssetConfig.model_validate(
        build_revenue_operations_outcome_pack_config()
    )


def test_revenue_operations_flagship_is_structurally_complete() -> None:
    config = _config()

    assert config.marketplace_version == "3.0"
    assert tuple(play.key for play in config.plays) == REVENUE_OPERATIONS_PLAY_KEYS
    assert len(config.plays) == 8
    assert len(config.agents) == 6
    assert len(config.knowledge) == 5
    assert len(config.dataset.entities) >= 7
    assert len(config.outcome_contract.kpis) == 12
    assert {metric.kpi_key for metric in config.dashboard.metrics} == {
        kpi.key for kpi in config.outcome_contract.kpis
    }


def test_revenue_operations_fixture_contracts_pass() -> None:
    config = _config()
    failed = [check for check in fixture_checks(config) if not check.passed]
    assert failed == [], [check.as_dict() for check in failed]


def test_revenue_operations_is_governed_not_production_verified() -> None:
    config = _config()
    report = certify_outcome_pack(config)

    assert report.level == "governed"
    assert report.publish_ready is False
    assert report.unresolved_skill_requirements == []
    assert config.runtime_profiles[0].provider == "hubspot"
    assert config.runtime_profiles[0].status == "tested"


def test_revenue_operations_follow_up_is_preparation_only() -> None:
    config = _config()
    follow_up = next(play for play in config.plays if play.key == "post-meeting-follow-up")

    assert follow_up.approvals == [
        {"when": "send_external_message_or_crm_write", "required": True}
    ]
    assert follow_up.verification["provider_acceptance_is_terminal"] is False
    actions = {
        str((step.get("config") or {}).get("action") or "")
        for step in follow_up.workflow_steps
        if step.get("type") == "invoke_tool"
    }
    assert actions == {"hubspot.deals.get"}


def test_revenue_operations_runtime_profile_contains_only_declared_hubspot_reads() -> None:
    config = _config()
    profile = config.runtime_profiles[0]

    assert profile.provider == "hubspot"
    assert set(profile.actions) == {
        "hubspot.contacts.search",
        "hubspot.companies.search",
        "hubspot.deals.get",
        "hubspot.deals.search",
        "hubspot.deals.list",
        "hubspot.owners.list",
        "hubspot.pipelines.list",
    }


def test_revenue_operations_outcome_events_match_play_events() -> None:
    config = _config()
    declared = set(config.outcome_contract.outcome_events)
    play_events = {event for play in config.plays for event in play.outcome_events}

    assert play_events == declared
    assert "post_meeting_follow_up_prepared" in declared
    assert "forecast_integrity_reviewed" in declared


def test_department_portfolio_uses_dedicated_revenue_flagship() -> None:
    outcome_assets = [
        asset
        for asset in department_portfolio_marketplace3_assets()
        if asset.asset_type == "outcome_pack" and asset.slug == "revenue-operations-3"
    ]
    assert len(outcome_assets) == 1
    config = OutcomePackAssetConfig.model_validate(outcome_assets[0].config)
    assert tuple(play.key for play in config.plays) == REVENUE_OPERATIONS_PLAY_KEYS
    assert len(config.agents) == 6
    assert len(config.outcome_contract.kpis) == 12
    assert config.dashboard.title == "Revenue Operations Command Center"
