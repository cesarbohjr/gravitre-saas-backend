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


def test_msp_service_desk_v1_is_governed_but_not_self_certified() -> None:
    report = certify_outcome_pack(_msp_config())

    assert report.publish_ready is False
    assert report.level == "governed"
    assert report.unresolved_skill_requirements == []
    assert "freshservice.tickets.update_status" in report.runtime_actions
    assert not any(finding.code == "WRITE_APPROVAL_MISSING" for finding in report.findings)


def test_production_verified_requires_evidence_linked_live_action_proof() -> None:
    payload = deepcopy(build_msp_service_desk_outcome_pack_config())
    payload["runtime_profiles"][0]["status"] = "production_verified"
    config = OutcomePackAssetConfig.model_validate(payload)

    without_evidence = certify_outcome_pack(config)
    with_evidence = certify_outcome_pack(
        config,
        runtime_evidence={
            "freshservice": {
                "environment": "production",
                "evidence_ref": "workflow_run:live-smoke-123",
                "verified_actions": payload["runtime_profiles"][0]["actions"],
            }
        },
    )

    assert without_evidence.publish_ready is False
    assert without_evidence.level == "governed"
    assert any(f.code == "PRODUCTION_EVIDENCE_MISSING" for f in without_evidence.findings)
    assert with_evidence.publish_ready is True
    assert with_evidence.level == "production_verified"


def test_msp_service_desk_fails_closed_if_skill_binding_is_removed() -> None:
    payload = deepcopy(build_msp_service_desk_outcome_pack_config())
    payload["skill_bindings"].pop("ticket-triage")

    report = certify_outcome_pack(OutcomePackAssetConfig.model_validate(payload))

    assert report.publish_ready is False
    assert "ticket-triage" in report.unresolved_skill_requirements


def test_outcome_verified_requires_production_and_measured_outcome_evidence() -> None:
    payload = deepcopy(build_msp_service_desk_outcome_pack_config())
    payload["runtime_profiles"][0]["status"] = "production_verified"
    config = OutcomePackAssetConfig.model_validate(payload)
    runtime_evidence = {
        "freshservice": {
            "environment": "production",
            "evidence_ref": "workflow_run:live-smoke-123",
            "verified_actions": payload["runtime_profiles"][0]["actions"],
        }
    }
    without_outcome = certify_outcome_pack(config, runtime_evidence=runtime_evidence)
    with_outcome = certify_outcome_pack(
        config,
        runtime_evidence=runtime_evidence,
        outcome_evidence={"measurements": [{
            "evidenceId": "event-1", "orgId": "org-1", "runId": "run-1",
            "measuredAt": "2026-10-02T12:00:00Z", "verificationMethod": "source_read",
            "playKey": next(p.key for p in config.plays if "ticket_sla_saved" in p.outcome_events),
            "metricKey": next(p.kpi_keys[0] for p in config.plays if "ticket_sla_saved" in p.outcome_events),
            "outcomeEvent": "ticket_sla_saved", "baselineValue": 2, "resultValue": 1,
            "sourceRecords": [{"system": "freshservice", "record_type": "ticket", "record_id": "42"}],
        }]},
    )

    assert without_outcome.level == "production_verified"
    assert with_outcome.level == "outcome_verified"
