from app.marketplace.marketplace3.msp_service_desk import (
    MSP_SERVICE_DESK_PLAY_KEYS,
    build_msp_service_desk_outcome_pack_config,
)
from app.marketplace.schemas import OutcomePackAssetConfig


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


def test_msp_service_desk_blueprint_remains_unpublished_blueprint_only() -> None:
    payload = build_msp_service_desk_outcome_pack_config()
    assert "status" not in payload
    assert "visibility" not in payload
    assert payload["marketplace_version"] == "3.0"


def test_msp_service_desk_declares_real_psa_alternatives_without_overclaiming_runtime_verification() -> None:
    payload = build_msp_service_desk_outcome_pack_config()
    psa_group = payload["connector_alternatives"][0]
    assert {
        "freshservice",
        "zendesk",
        "halo_psa",
        "autotask",
        "syncro",
        "servicenow",
    } <= set(psa_group)
    assert payload["runtime_profiles"] == [
        {
            "provider": "freshservice",
            "status": "implementation",
            "actions": [
                "freshservice.tickets.list",
                "freshservice.tickets.get",
                "freshservice.tickets.activities",
                "freshservice.tickets.update_status",
            ],
        }
    ]
