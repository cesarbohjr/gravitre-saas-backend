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


def test_msp_service_desk_blueprint_cannot_self_certify_for_freshservice() -> None:
    report = certify_outcome_pack(_msp_config())

    assert report.publish_ready is False
    assert report.level == "governed"
    assert report.unresolved_skill_requirements == []
    assert "freshservice.tickets.update_status" in report.runtime_actions
    assert not any(finding.blocking for finding in report.findings)


def test_msp_service_desk_fails_closed_if_skill_binding_is_removed() -> None:
    payload = deepcopy(build_msp_service_desk_outcome_pack_config())
    payload["skill_bindings"].pop("ticket-triage")

    report = certify_outcome_pack(OutcomePackAssetConfig.model_validate(payload))

    assert report.publish_ready is False
    assert "ticket-triage" in report.unresolved_skill_requirements


def test_outcome_verified_requires_measured_verified_outcome_event() -> None:
    config = _msp_config()
    without_evidence = certify_outcome_pack(config)
    with_evidence = certify_outcome_pack(
        config,
        outcome_evidence={"verified_outcome_events": ["ticket_sla_saved"]},
    )

    assert without_evidence.level == "governed"
    assert with_evidence.level == "governed"


def test_production_requires_complete_independent_evidence_not_runtime_labels():
    from app.marketplace.marketplace3.production_evidence import ProductionEvidence, REQUIRED_CHECKS
    config = _msp_config()
    actions = {action for profile in config.runtime_profiles for action in profile.actions}
    proof = ProductionEvidence("org", "pack", "digest", frozenset(actions), {key: True for key in REQUIRED_CHECKS}, ("run",))
    assert not certify_outcome_pack(config, production_evidence=proof).publish_ready
    report = certify_outcome_pack(config, production_evidence=proof, resolved_skill_ids=set(config.skill_bindings.values()))
    assert report.publish_ready
    assert report.level == "production_verified"
    assert not certify_outcome_pack(config, production_evidence={"actions": list(actions), "passed": True}).publish_ready
