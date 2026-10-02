from __future__ import annotations

from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.marketplace3.certification_runner import (
    CertificationRunnerError,
    _fixture_checks,
    run_outcome_pack_certification,
)
from app.marketplace.marketplace3.msp_service_desk import (
    build_msp_service_desk_outcome_pack_config,
)
from app.marketplace.schemas import OutcomePackAssetConfig


ORG_ID = "11111111-1111-1111-1111-111111111111"
ASSET_ID = "22222222-2222-2222-2222-222222222222"


def _config() -> OutcomePackAssetConfig:
    return OutcomePackAssetConfig.model_validate(
        build_msp_service_desk_outcome_pack_config()
    )


def _asset_table(asset: dict):
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(data=[asset])
    return table


def test_fixture_checks_cover_kpis_agents_runtime_governance_and_events() -> None:
    checks = _fixture_checks(_config())
    by_key = {check.key: check for check in checks}
    assert {
        "kpi_contract_coverage",
        "play_agent_bindings",
        "runtime_actions_registered",
        "write_governance_contract",
        "outcome_event_contract",
    } <= set(by_key)
    assert all(check.passed for check in checks)


def test_fixture_checks_fail_when_dataset_kpi_contract_drifts() -> None:
    payload = deepcopy(build_msp_service_desk_outcome_pack_config())
    payload["dataset"]["metrics"] = [
        row for row in payload["dataset"]["metrics"] if row["key"] != "mttr"
    ]
    config = OutcomePackAssetConfig.model_validate(payload)
    by_key = {check.key: check for check in _fixture_checks(config)}
    assert by_key["kpi_contract_coverage"].passed is False
    assert "mttr" in by_key["kpi_contract_coverage"].metadata["missingDatasetKpis"]


@patch("app.marketplace.marketplace3.certification_runner.certify_and_record_outcome_pack")
def test_fixture_runner_never_promotes_fixture_proof_to_production(mock_record) -> None:
    asset = {
        "id": ASSET_ID,
        "org_id": ORG_ID,
        "slug": "msp-service-desk-3",
        "asset_type": "outcome_pack",
        "config": build_msp_service_desk_outcome_pack_config(),
    }
    client = MagicMock()
    client.table.return_value = _asset_table(asset)
    mock_record.return_value = {
        "assetId": ASSET_ID,
        "level": "compatible",
        "publishReady": False,
    }

    result = run_outcome_pack_certification(
        client,
        org_id=ORG_ID,
        asset_ref=ASSET_ID,
        actor_id="admin-1",
        mode="fixture",
    )

    assert result["fixturePassed"] is True
    evidence = mock_record.call_args.kwargs["evidence"]
    assert evidence["runner_mode"] == "fixture"
    assert evidence["fixture_checks_passed"] is True
    assert evidence["fresh_install_passed"] is False
    assert evidence["golden_path_passed"] is False
    assert evidence["failure_path_passed"] is False
    assert evidence["permissions_passed"] is False
    assert evidence["kpi_reconciliation_passed"] is False
    assert evidence["source_of_record_verification_passed"] is False


def test_production_mode_fails_closed_without_live_provider_runner() -> None:
    asset = {
        "id": ASSET_ID,
        "org_id": ORG_ID,
        "slug": "msp-service-desk-3",
        "asset_type": "outcome_pack",
        "config": build_msp_service_desk_outcome_pack_config(),
    }
    client = MagicMock()
    client.table.return_value = _asset_table(asset)

    with pytest.raises(CertificationRunnerError) as exc:
        run_outcome_pack_certification(
            client,
            org_id=ORG_ID,
            asset_ref=ASSET_ID,
            actor_id="admin-1",
            mode="production",
        )
    assert exc.value.code == "LIVE_PROVIDER_RUNNER_REQUIRED"
