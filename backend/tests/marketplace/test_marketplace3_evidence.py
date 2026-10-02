from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.marketplace3.certification import OutcomePackCertification
from app.marketplace.marketplace3.evidence import (
    MarketplaceCertificationEvidenceError,
    _config_with_evidence_status,
    certification_target_version,
    record_runtime_evidence,
)
from app.marketplace.marketplace3.msp_service_desk import (
    build_msp_service_desk_outcome_pack_config,
)
from app.marketplace.schemas import OutcomePackAssetConfig


def _asset(**overrides) -> dict:
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "org_id": "22222222-2222-2222-2222-222222222222",
        "asset_type": "outcome_pack",
        "status": "draft",
        "current_version": 1,
        "config": build_msp_service_desk_outcome_pack_config(),
    }
    base.update(overrides)
    return base


def test_certification_evidence_targets_candidate_version_before_publish() -> None:
    assert certification_target_version(_asset(status="draft", current_version=4)) == 5
    assert certification_target_version(_asset(status="pending_review", current_version=4)) == 5
    assert certification_target_version(_asset(status="published", current_version=4)) == 4


def test_runtime_evidence_rejects_non_production() -> None:
    with pytest.raises(MarketplaceCertificationEvidenceError) as exc:
        record_runtime_evidence(
            MagicMock(),
            asset=_asset(),
            provider="freshservice",
            environment="staging",
            evidence_ref="workflow_run:smoke-1",
            verified_actions=["freshservice.tickets.get"],
            actor_id="admin-1",
        )
    assert exc.value.code == "NON_PRODUCTION_EVIDENCE"


def test_runtime_evidence_rejects_undeclared_action() -> None:
    with pytest.raises(MarketplaceCertificationEvidenceError) as exc:
        record_runtime_evidence(
            MagicMock(),
            asset=_asset(),
            provider="freshservice",
            environment="production",
            evidence_ref="workflow_run:smoke-1",
            verified_actions=["freshservice.not_a_declared_action"],
            actor_id="admin-1",
        )
    assert exc.value.code == "UNDECLARED_ACTIONS"


def test_runtime_profile_elevates_only_after_all_declared_actions_have_evidence() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_msp_service_desk_outcome_pack_config()
    )
    profile = config.runtime_profiles[0]
    partial = {
        profile.provider: {
            "environment": "production",
            "evidence_ref": "workflow_run:smoke-1",
            "verified_actions": list(profile.actions[:-1]),
        }
    }
    complete = deepcopy(partial)
    complete[profile.provider]["verified_actions"] = list(profile.actions)

    partial_config = _config_with_evidence_status(config, partial)
    complete_config = _config_with_evidence_status(config, complete)

    assert partial_config.runtime_profiles[0].status != "production_verified"
    assert complete_config.runtime_profiles[0].status == "production_verified"


@patch("app.marketplace.marketplace3.evidence.certification_report_for_asset")
def test_record_runtime_evidence_is_immutable_and_returns_certification(mock_report) -> None:
    asset = _asset()
    profile = OutcomePackAssetConfig.model_validate(asset["config"]).runtime_profiles[0]
    table = MagicMock()
    table.insert.return_value = table
    table.execute.return_value = MagicMock(
        data=[
            {
                "id": "evidence-1",
                "asset_id": asset["id"],
                "asset_version": 2,
                "evidence_ref": "workflow_run:smoke-123",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = table
    mock_report.return_value = OutcomePackCertification(
        level="production_verified",
        publish_ready=True,
        findings=[],
        play_count=8,
        runtime_actions=list(profile.actions),
        verified_skills=[],
        unresolved_skill_requirements=[],
    )

    result = record_runtime_evidence(
        client,
        asset=asset,
        provider=profile.provider,
        environment="production",
        evidence_ref="workflow_run:smoke-123",
        verified_actions=list(profile.actions),
        actor_id="admin-1",
    )

    payload = table.insert.call_args.args[0]
    assert payload["asset_version"] == 2
    assert payload["evidence_kind"] == "runtime"
    assert payload["verified_actions"] == sorted(profile.actions)
    assert result["certification"]["level"] == "production_verified"



def test_certification_evidence_migration_keeps_raw_evidence_backend_only() -> None:
    migration = (
        Path(__file__).resolve().parents[3]
        / "supabase/migrations/20261002160000_marketplace3_certification_evidence.sql"
    )
    sql = migration.read_text(encoding="utf-8")
    assert "alter table public.marketplace_certification_evidence enable row level security" in sql.lower()
    assert "create policy" not in sql.lower()
    assert "unique (asset_id, asset_version, evidence_ref)" in sql.lower()
