from __future__ import annotations

from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.marketplace3.certification_store import (
    OutcomePackCertificationError,
    assert_outcome_pack_publish_ready,
    certify_and_record_outcome_pack,
    get_outcome_pack_certification,
    outcome_pack_config_digest,
)
from app.marketplace.marketplace3.msp_service_desk import (
    build_msp_service_desk_outcome_pack_config,
)


ORG_ID = "11111111-1111-1111-1111-111111111111"
ASSET_ID = "22222222-2222-2222-2222-222222222222"


def _table(*, data=None):
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.upsert.return_value = table
    table.execute.return_value = MagicMock(data=data or [])
    return table


def test_outcome_pack_digest_is_canonical_and_changes_with_config() -> None:
    config = build_msp_service_desk_outcome_pack_config()
    reordered = {key: config[key] for key in reversed(list(config))}
    assert outcome_pack_config_digest(config) == outcome_pack_config_digest(reordered)

    changed = deepcopy(config)
    changed["outcome_contract"]["target_outcome"] += " Changed."
    assert outcome_pack_config_digest(changed) != outcome_pack_config_digest(config)


@patch("app.marketplace.marketplace3.certification_store.certify_outcome_pack")
def test_certify_and_record_binds_report_to_exact_config_digest(mock_certify) -> None:
    report = MagicMock()
    report.level = "production_verified"
    report.publish_ready = True
    report.as_dict.return_value = {
        "level": "production_verified",
        "publishReady": True,
        "findings": [],
    }
    mock_certify.return_value = report

    table = _table()
    table.execute.return_value = MagicMock(
        data=[
            {
                "id": "cert-1",
                "certified_at": "2026-10-02T00:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = table
    config = build_msp_service_desk_outcome_pack_config()

    result = certify_and_record_outcome_pack(
        client,
        org_id=ORG_ID,
        asset_id=ASSET_ID,
        config=config,
        actor_id="admin-1",
        resolved_skill_ids={"skill-1"},
        evidence={"fresh_install_passed": True},
    )

    payload = table.upsert.call_args.args[0]
    assert payload["config_digest"] == outcome_pack_config_digest(config)
    assert payload["publish_ready"] is True
    assert payload["certification_level"] == "production_verified"
    assert result["publishReady"] is True


def test_get_certification_returns_none_when_current_digest_has_no_record() -> None:
    client = MagicMock()
    client.table.return_value = _table(data=[])
    assert (
        get_outcome_pack_certification(
            client,
            org_id=ORG_ID,
            asset_id=ASSET_ID,
            config=build_msp_service_desk_outcome_pack_config(),
        )
        is None
    )


@patch("app.marketplace.marketplace3.certification_store.get_outcome_pack_certification", return_value=None)
def test_publish_ready_gate_rejects_missing_certification(_mock_get) -> None:
    with pytest.raises(OutcomePackCertificationError) as exc:
        assert_outcome_pack_publish_ready(
            MagicMock(),
            org_id=ORG_ID,
            asset_id=ASSET_ID,
            config=build_msp_service_desk_outcome_pack_config(),
        )
    assert exc.value.details["reason"] == "certification_missing"


@patch(
    "app.marketplace.marketplace3.certification_store.get_outcome_pack_certification",
    return_value={
        "level": "governed",
        "publishReady": False,
        "report": {"findings": [{"code": "PRODUCTION_EVIDENCE_MISSING"}]},
    },
)
def test_publish_ready_gate_rejects_non_production_certification(_mock_get) -> None:
    with pytest.raises(OutcomePackCertificationError) as exc:
        assert_outcome_pack_publish_ready(
            MagicMock(),
            org_id=ORG_ID,
            asset_id=ASSET_ID,
            config=build_msp_service_desk_outcome_pack_config(),
        )
    assert exc.value.details["reason"] == "certification_not_publish_ready"
    assert exc.value.details["level"] == "governed"


@patch(
    "app.marketplace.marketplace3.certification_store.get_outcome_pack_certification",
    return_value={
        "level": "production_verified",
        "publishReady": True,
        "report": {"findings": []},
    },
)
def test_publish_ready_gate_accepts_current_production_verified_record(_mock_get) -> None:
    result = assert_outcome_pack_publish_ready(
        MagicMock(),
        org_id=ORG_ID,
        asset_id=ASSET_ID,
        config=build_msp_service_desk_outcome_pack_config(),
    )
    assert result["level"] == "production_verified"
