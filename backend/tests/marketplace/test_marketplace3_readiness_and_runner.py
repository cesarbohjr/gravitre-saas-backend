from app.marketplace.marketplace3.connector_groups import evaluate_connector_or_groups
from app.marketplace.marketplace3.discovery import outcome_pack_discovery_metadata
from app.marketplace.marketplace3.msp_service_desk import (
    build_msp_service_desk_outcome_pack_config,
)
from app.marketplace.marketplace3.pack_audit import audit_catalog_packs
from app.marketplace.marketplace3.certification_runner import fixture_checks
from app.marketplace.schemas import OutcomePackAssetConfig


def test_psa_or_group_is_satisfied_by_any_registered_alternative() -> None:
    result = evaluate_connector_or_groups(
        connected={"halo_psa"},
        required_connectors=[{"connectorType": "freshservice", "required": True}],
        alternatives=[["freshservice", "halo_psa", "autotask", "connectwise", "syncro"]],
    )
    assert result["can_install"] is True
    assert result["groups"][0]["satisfied"] is True


def test_psa_or_group_blocks_when_no_member_is_connected() -> None:
    result = evaluate_connector_or_groups(
        connected={"slack"},
        required_connectors=[{"connectorType": "freshservice", "required": True}],
        alternatives=[["freshservice", "halo_psa", "autotask"]],
    )
    assert result["can_install"] is False
    assert "halo_psa" in result["blockers"][0]["alternatives"]


def test_msp_runner_fixtures_pass_without_granting_production_verified() -> None:
    config = OutcomePackAssetConfig.model_validate(build_msp_service_desk_outcome_pack_config())
    checks = {row.key: row for row in fixture_checks(config)}
    assert checks["minimum_plays"].passed is True
    assert checks["kpi_contract_coverage"].passed is True
    assert checks["play_agent_bindings"].passed is True
    assert checks["outcome_event_contract"].passed is True
    assert all(check.passed for check in checks.values())
    discovery = outcome_pack_discovery_metadata(config, connected_vendors={"freshservice"})
    assert discovery["playCount"] == 8
    assert discovery["supportedPlayCount"] == 8
    assert "halo_psa" in discovery["supportedSystems"]


def test_legacy_pack_audit_does_not_delete_or_promote_incomplete_packs() -> None:
    report = audit_catalog_packs()
    assert report["legacyCount"] >= 1
    legacy = next(row for row in report["packs"] if not row["marketplace3"] and row["assetType"] == "department_pack")
    assert "missing Plays" in legacy["gaps"] or "missing outcome contracts" in legacy["gaps"]
    assert "Rebuild" in (legacy["replacement"] or "")
