from __future__ import annotations

from copy import deepcopy

from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.msp_service_desk import (
    build_msp_service_desk_outcome_pack_config,
)
from app.marketplace.schemas import OutcomePackAssetConfig


def _msp_config() -> OutcomePackAssetConfig:
    return OutcomePackAssetConfig.model_validate(
        build_msp_service_desk_outcome_pack_config()
    )


def test_msp_blueprint_is_not_publish_ready_until_real_dependencies_are_verified() -> None:
    report = certify_outcome_pack(_msp_config())
    codes = {finding.code for finding in report.findings}

    assert report.publish_ready is False
    assert report.level == "compatible"
    assert "SKILL_REQUIREMENTS_UNRESOLVED" in codes
    assert "RUNTIME_ACTION_NOT_REGISTERED" not in codes
    assert "WRITE_APPROVAL_MISSING" not in codes
    assert "WRITE_VERIFICATION_INCOMPLETE" not in codes


def _production_evidence() -> dict:
    return {
        "fresh_install_passed": True,
        "golden_path_passed": True,
        "failure_path_passed": True,
        "permissions_passed": True,
        "kpi_reconciliation_passed": True,
        "source_of_record_verification_passed": True,
    }


def _production_ready_payload() -> dict:
    payload = deepcopy(build_msp_service_desk_outcome_pack_config())
    skill_ids = []
    bindings = {}
    for index, requirement in enumerate(payload["skill_requirements"]):
        package_id = f"verified-skill-{index}"
        bindings[requirement] = package_id
        skill_ids.append(package_id)
    payload["skill_bindings"] = bindings
    payload["skills"] = skill_ids
    for profile in payload["runtime_profiles"]:
        profile["status"] = "production_verified"
    return payload


def test_runtime_status_and_skill_bindings_alone_do_not_grant_production_verified() -> None:
    payload = _production_ready_payload()

    report = certify_outcome_pack(OutcomePackAssetConfig.model_validate(payload))

    assert report.publish_ready is False
    assert report.level == "governed"
    assert any(f.code == "PRODUCTION_EVIDENCE_MISSING" for f in report.findings)


def test_msp_blueprint_can_reach_production_verified_with_real_evidence() -> None:
    payload = _production_ready_payload()

    report = certify_outcome_pack(
        OutcomePackAssetConfig.model_validate(payload),
        outcome_evidence=_production_evidence(),
    )

    assert report.publish_ready is True
    assert report.level == "production_verified"
    assert report.unresolved_skill_requirements == []


def test_outcome_verified_requires_measured_verified_outcome_event() -> None:
    payload = _production_ready_payload()
    config = OutcomePackAssetConfig.model_validate(payload)
    production_evidence = _production_evidence()
    without_outcome = certify_outcome_pack(
        config,
        outcome_evidence=production_evidence,
    )
    with_evidence = certify_outcome_pack(
        config,
        outcome_evidence={
            **production_evidence,
            "verified_outcome_events": ["ticket_sla_saved"],
        },
    )

    assert without_outcome.level == "production_verified"
    assert with_evidence.level == "outcome_verified"
