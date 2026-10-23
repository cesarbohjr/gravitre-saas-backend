from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.marketplace3.certification_store import (
    OutcomePackCertificationError,
    assert_outcome_pack_publish_ready,
    certify_and_record_outcome_pack,
    get_outcome_pack_certification,
    outcome_pack_config_digest,
)
from app.marketplace.schemas import OutcomePackAssetConfig
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
    table.gt.return_value = table
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
    config = build_msp_service_desk_outcome_pack_config()
    asset_table = _table(data=[{"id": ASSET_ID, "org_id": ORG_ID, "asset_type": "outcome_pack", "config": config}])
    workflow_table = _table()
    workflow_table.gte.return_value = workflow_table
    check_table = _table()
    check_table.gte.return_value = check_table
    check_table.order.return_value = check_table
    client.table.side_effect = lambda name: {"marketplace_assets": asset_table,
        "workflow_runs": workflow_table, "marketplace_outcome_pack_checks": check_table, "marketplace_outcome_pack_certifications": table}[name]

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
    assert timedelta(days=29) < (datetime.fromisoformat(payload["expires_at"]) - datetime.fromisoformat(payload["certified_at"])) <= timedelta(days=30, seconds=1)
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
@patch("app.marketplace.marketplace3.certification_store.collect_reviewed_skill_ids")
def test_publish_ready_gate_accepts_current_production_verified_record(mock_skills, _mock_get) -> None:
    mock_skills.return_value = set(build_msp_service_desk_outcome_pack_config()["skill_bindings"].values())
    result = assert_outcome_pack_publish_ready(
        MagicMock(),
        org_id=ORG_ID,
        asset_id=ASSET_ID,
        config=build_msp_service_desk_outcome_pack_config(),
    )
    assert result["level"] == "production_verified"


@pytest.mark.parametrize("visibility,owner,current,expected", [
    ("public", "publisher", True, True),
    ("private", ORG_ID, True, True),
    ("private", "foreign", True, False),
    ("public", "publisher", False, False),
])
def test_skill_provenance_requires_visible_current_approved_source(visibility, owner, current, expected):
    from app.marketplace.marketplace3.certification_store import collect_reviewed_skill_ids
    from app.marketplace.publish import MarketplacePublishError
    config = OutcomePackAssetConfig.model_validate(build_msp_service_desk_outcome_pack_config())
    slug = next(iter(config.skill_bindings.values()))
    config.skill_bindings = {"ticket-triage": slug}
    client = MagicMock()
    client.table.return_value = _table(data=[{
        "slug": slug, "org_id": owner, "visibility": visibility,
        "asset_type": "capability_package", "status": "published",
    }])
    with patch("app.marketplace.publish._assert_capability_provenance_current") as verify:
        if not current:
            verify.side_effect = MarketplacePublishError("snapshot changed", code="VALIDATION_ERROR")
        assert collect_reviewed_skill_ids(client, org_id=ORG_ID, config=config) == ({slug} if expected else set())


def test_publish_rechecks_skill_approval_after_certificate_issuance():
    with patch("app.marketplace.marketplace3.certification_store.get_outcome_pack_certification", return_value={"level": "production_verified", "publishReady": True}), patch("app.marketplace.marketplace3.certification_store.collect_reviewed_skill_ids", return_value=set()):
        with pytest.raises(OutcomePackCertificationError) as exc:
            assert_outcome_pack_publish_ready(MagicMock(), org_id=ORG_ID, asset_id=ASSET_ID, config=build_msp_service_desk_outcome_pack_config())
    assert exc.value.details["reason"] == "skill_provenance_changed"
