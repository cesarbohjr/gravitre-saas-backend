from app.capabilities.provenance import inert_snapshot_digest
from app.marketplace.marketplace3.msp_service_desk import (
    MSP_SERVICE_DESK_PLAY_KEYS,
    build_msp_service_desk_outcome_pack_config,
    build_msp_service_desk_skill_package_config,
    msp_service_desk_marketplace3_assets,
)
from app.marketplace.schemas import OutcomePackAssetConfig, parse_asset_config


def test_msp_service_desk_blueprint_is_valid_marketplace3_outcome_pack() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_msp_service_desk_outcome_pack_config()
    )
    assert config.marketplace_version == "3.0"
    assert len(config.plays) == 8
    assert {play.key for play in config.plays} == set(MSP_SERVICE_DESK_PLAY_KEYS)
    assert len(config.agents) == 3
    assert len(config.outcome_contract.kpis) >= 10
    assert {
        metric.kpi_key for metric in config.dashboard.metrics
    } == {kpi.key for kpi in config.outcome_contract.kpis}
    assert config.runtime_profiles[0].provider == "freshservice"
    assert config.runtime_profiles[0].status == "production_verified"
    assert "freshservice.tickets.update_status" in config.runtime_profiles[0].actions
    inputs_by_play = {play.key: set(play.runtime_inputs) for play in config.plays}
    assert inputs_by_play["intelligent-ticket-intake"] == {"TICKET_ID"}
    assert inputs_by_play["sla-rescue"] == {"TICKET_ID", "TARGET_STATUS"}


def test_msp_service_desk_skill_package_is_publishable_and_git_pinned() -> None:
    config = build_msp_service_desk_skill_package_config()
    parsed = parse_asset_config("capability_package", config, publish=True)
    assert parsed.provenance_mode == "git_pinned"
    assert parsed.commit_sha == "e35e61a5b6fd499895cf526930187383aed36027"
    assert parsed.package_format == "gravitre"
    assert parsed.risk_level == "low"
    assert inert_snapshot_digest(
        manifest=config["manifest"],
        resources=config["resources"],
    ) == config["snapshot_digest"]


def test_msp_service_desk_catalog_contains_complete_marketplace3_bundle() -> None:
    assets = msp_service_desk_marketplace3_assets()
    types = [asset.asset_type for asset in assets]
    slugs = {asset.slug for asset in assets}
    outcome = next(asset for asset in assets if asset.asset_type == "outcome_pack")

    assert types.count("ai_agent") == 3
    assert types.count("play") == 8
    assert types.count("capability_package") == 1
    assert types.count("knowledge_pack") == 1
    assert types.count("dataset_pack") == 1
    assert types.count("dashboard_pack") == 1
    assert types.count("outcome_pack") == 1
    assert "msp-service-desk-skills-v1" in slugs
    assert len(outcome.pack_children) == 15
    assert set(outcome.pack_children) <= slugs
    parse_asset_config("outcome_pack", outcome.config, publish=True)
