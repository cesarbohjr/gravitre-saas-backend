from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.marketplace.marketplace3.msp_service_desk import (
    build_msp_service_desk_outcome_pack_config,
)
from app.marketplace.marketplace3.production_evidence import (
    collect_production_evidence,
)
from app.marketplace.schemas import OutcomePackAssetConfig


ORG_ID = "11111111-1111-1111-1111-111111111111"
ASSET_ID = "22222222-2222-2222-2222-222222222222"


def _query(data):
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.in_.return_value = q
    q.order.return_value = q
    q.limit.return_value = q
    q.execute.return_value = MagicMock(data=data)
    return q


def _config():
    return OutcomePackAssetConfig.model_validate(
        build_msp_service_desk_outcome_pack_config()
    )


@patch("app.marketplace.marketplace3.production_evidence.get_action_spec")
def test_production_evidence_does_not_treat_read_or_unverified_run_as_write_proof(mock_spec):
    read_spec = MagicMock()
    read_spec.kind = "read"
    mock_spec.return_value = read_spec

    play_installs = _query(
        [
            {
                "id": "pi-1",
                "play_key": "intelligent-ticket-intake",
                "status": "active",
                "environment_name": "production",
                "configuration": {"marketplaceAssetId": ASSET_ID},
            }
        ]
    )
    dataset = _query([{"id": "dataset-1", "asset_id": ASSET_ID, "status": "active"}])
    dashboard = _query([{"id": "dash-1", "asset_id": ASSET_ID, "status": "active"}])
    play_runs = _query(
        [
            {
                "id": "pr-1",
                "installation_id": "pi-1",
                "play_key": "intelligent-ticket-intake",
                "status": "completed",
                "workflow_run_ids": ["wr-1"],
                "metadata": {"certificationScenario": "golden_path", "certificationExpected": True},
            }
        ]
    )
    workflows = _query(
        [
            {
                "id": "wr-1",
                "status": "completed",
                "parameters": {
                    "invoke_action": "freshservice.tickets.get",
                    "verification_status": "verified",
                    "verification": {"verified": True},
                },
            }
        ]
    )
    outcomes = _query([])

    client = MagicMock()
    client.table.side_effect = [
        play_installs,
        dataset,
        dashboard,
        play_runs,
        workflows,
        outcomes,
    ]

    evidence = collect_production_evidence(
        client,
        org_id=ORG_ID,
        asset_id=ASSET_ID,
        config=_config(),
    )

    assert evidence["source_of_record_verification_passed"] is False
    assert evidence["permissions_passed"] is False


@patch("app.marketplace.marketplace3.production_evidence.get_action_spec")
def test_production_evidence_accepts_only_verified_declared_mutating_run(mock_spec):
    write_spec = MagicMock()
    write_spec.kind = "update"
    mock_spec.return_value = write_spec

    play_installs = _query(
        [
            {
                "id": "pi-1",
                "play_key": "intelligent-ticket-intake",
                "status": "active",
                "environment_name": "production",
                "configuration": {"marketplaceAssetId": ASSET_ID},
            }
        ]
    )
    dataset = _query([{"id": "dataset-1", "asset_id": ASSET_ID, "status": "active"}])
    dashboard = _query([{"id": "dash-1", "asset_id": ASSET_ID, "status": "active"}])
    play_runs = _query(
        [
            {
                "id": "pr-1",
                "installation_id": "pi-1",
                "play_key": "intelligent-ticket-intake",
                "status": "completed",
                "workflow_run_ids": ["wr-1"],
                "metadata": {},
            }
        ]
    )
    workflows = _query(
        [
            {
                "id": "wr-1",
                "status": "completed",
                "parameters": {
                    "invoke_action": "freshservice.tickets.update_status",
                    "verification_status": "verified",
                    "verification": {
                        "verified": True,
                        "kind": "field_assert",
                        "entity_id": "ticket-1",
                    },
                },
            }
        ]
    )
    outcomes = _query([])

    client = MagicMock()
    client.table.side_effect = [
        play_installs,
        dataset,
        dashboard,
        play_runs,
        workflows,
        outcomes,
    ]

    evidence = collect_production_evidence(
        client,
        org_id=ORG_ID,
        asset_id=ASSET_ID,
        config=_config(),
    )

    assert evidence["source_of_record_verification_passed"] is True
    assert evidence["proof"]["verifiedWriteRuns"][0]["action"] == "freshservice.tickets.update_status"
