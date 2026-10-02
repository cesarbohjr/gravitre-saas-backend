from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.marketplace.marketplace3.certification_service import (
    Marketplace3CertificationError,
    certify_asset,
    promote_certified_asset,
)
from app.marketplace.marketplace3.msp_service_desk import (
    build_msp_service_desk_outcome_pack_config,
)


class _AssetTable:
    def __init__(self, row: dict):
        self.row = row
        self.pending_update: dict = {}

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def update(self, payload: dict):
        self.pending_update = dict(payload)
        self.row.update(payload)
        return self

    def execute(self):
        return SimpleNamespace(data=[dict(self.row)])


class _Client:
    def __init__(self, row: dict):
        self.assets = _AssetTable(row)

    def table(self, name: str):
        assert name == "marketplace_assets"
        return self.assets


def _asset(*, production_profile: bool = False) -> dict:
    config = deepcopy(build_msp_service_desk_outcome_pack_config())
    if production_profile:
        for profile in config["runtime_profiles"]:
            profile["status"] = "production_verified"
    return {
        "id": "asset-1",
        "slug": "msp-service-desk-3",
        "title": "MSP Service Desk 3.0",
        "asset_type": "outcome_pack",
        "status": "draft",
        "visibility": "internal",
        "tags": ["msp", "marketplace-3"],
        "verified": False,
        "published_at": None,
        "config": config,
        "certification_level": None,
        "certification_report": {},
        "certification_evidence": {},
    }


def _runtime_evidence(config: dict) -> dict:
    profile = config["runtime_profiles"][0]
    return {
        profile["provider"]: {
            "environment": "production",
            "evidence_ref": "workflow_run:prod-msp-smoke-001",
            "verified_actions": list(profile["actions"]),
        }
    }


def test_certification_persists_governed_state_without_live_proof() -> None:
    client = _Client(_asset())
    result = certify_asset(
        client,
        slug="msp-service-desk-3",
        actor_id="platform-1",
    )

    assert result["certification"]["level"] == "governed"
    assert result["certification"]["publishReady"] is False
    assert client.assets.row["certification_level"] == "governed"
    assert client.assets.row["certified_by"] == "platform-1"


def test_certification_rejects_secret_bearing_evidence() -> None:
    client = _Client(_asset())
    with pytest.raises(Marketplace3CertificationError) as exc:
        certify_asset(
            client,
            slug="msp-service-desk-3",
            actor_id="platform-1",
            runtime_evidence={
                "freshservice": {
                    "environment": "production",
                    "access_token": "must-not-persist",
                }
            },
        )
    assert exc.value.code == "EVIDENCE_SECRET_FORBIDDEN"


def test_promotion_fails_without_evidence_linked_production_certification() -> None:
    client = _Client(_asset())
    certify_asset(client, slug="msp-service-desk-3", actor_id="platform-1")

    with pytest.raises(Marketplace3CertificationError) as exc:
        promote_certified_asset(
            client,
            slug="msp-service-desk-3",
            actor_id="platform-1",
        )
    assert exc.value.code == "CERTIFICATION_REQUIRED"
    assert client.assets.row["status"] == "draft"
    assert client.assets.row["visibility"] == "internal"


def test_production_verified_pack_can_be_promoted_public() -> None:
    row = _asset(production_profile=True)
    client = _Client(row)
    runtime_evidence = _runtime_evidence(row["config"])

    certified = certify_asset(
        client,
        slug="msp-service-desk-3",
        actor_id="platform-1",
        runtime_evidence=runtime_evidence,
    )
    assert certified["certification"]["level"] == "production_verified"
    assert certified["certification"]["publishReady"] is True

    promoted = promote_certified_asset(
        client,
        slug="msp-service-desk-3",
        actor_id="platform-1",
    )

    assert promoted["promoted"] is True
    assert promoted["asset"]["status"] == "published"
    assert promoted["asset"]["visibility"] == "public"
    assert promoted["asset"]["verified"] is True
    assert "production-verified" in promoted["asset"]["tags"]


def test_outcome_evidence_promotes_highest_certification_level() -> None:
    row = _asset(production_profile=True)
    client = _Client(row)
    result = certify_asset(
        client,
        slug="msp-service-desk-3",
        actor_id="platform-1",
        runtime_evidence=_runtime_evidence(row["config"]),
        outcome_evidence={"verified_outcome_events": ["ticket_sla_saved"]},
    )
    assert result["certification"]["level"] == "outcome_verified"
    assert result["certification"]["publishReady"] is True
