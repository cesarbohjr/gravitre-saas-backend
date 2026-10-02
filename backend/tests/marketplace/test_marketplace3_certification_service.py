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


ORG = "00000000-0000-0000-0000-000000000001"
RUN = "00000000-0000-0000-0000-000000000002"
EVENT = "00000000-0000-0000-0000-000000000003"


class _EvidenceTable:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
    def select(self, *args):
        return self
    def eq(self, key, value):
        self.filters.append(lambda row: row.get(key) == value)
        return self
    def in_(self, key, values):
        self.filters.append(lambda row: row.get(key) in values)
        return self
    def execute(self):
        return SimpleNamespace(data=[row for row in self.rows if all(f(row) for f in self.filters)])


class _Client:
    def __init__(self, row: dict):
        self.assets = _AssetTable(row)
        play = next(p for p in row["config"]["plays"] if "ticket_sla_saved" in p["outcome_events"])
        self.evidence = {
            "workflow_runs": [{"id": RUN, "org_id": ORG, "run_type": "execute", "environment": "production", "status": "completed", "completed_at": "2026-10-02T12:00:00Z"}],
            "workflow_steps": [{"id": str(i), "org_id": ORG, "run_id": RUN, "status": "completed", "output_snapshot": {"invoke_action": action, "success": True, "verification": {"verified": True, "status": "verified"}}} for i, action in enumerate(row["config"]["runtime_profiles"][0]["actions"])],
            "intelligence_outcome_events": [{"id": EVENT, "org_id": ORG, "workflow_run_id": RUN, "outcome_event": "play_business_result", "measurement_status": "recorded", "before_value": 2, "after_value": 1, "measured_at": "2026-10-02T12:00:00Z", "metadata": {"contract": "play_business_result/v1", "play_key": play["key"], "metric_key": play["kpi_keys"][0], "outcome_type": "ticket_sla_saved", "verification_state": "VERIFIED SUCCESS", "verified": True, "verification_method": "source_read", "source_records": [{"system": "freshservice", "record_type": "ticket", "record_id": "42"}]}}],
        }

    def table(self, name: str):
        if name == "marketplace_assets":
            return self.assets
        return _EvidenceTable(self.evidence[name])


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
            "orgId": ORG,
            "runIds": [RUN],
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
        outcome_evidence={"orgId": ORG, "eventIds": [EVENT]},
    )
    assert result["certification"]["level"] == "outcome_verified"
    assert result["certification"]["publishReady"] is True


@pytest.mark.parametrize("change", ["dry_run", "digital_twin", "wrong_org", "failed", "missing_write_proof", "forged_actions", "simulated"])
def test_live_certification_rejects_unverified_runtime_claims(change):
    row = _asset(production_profile=True)
    client = _Client(row)
    evidence = _runtime_evidence(row["config"])
    run = client.evidence["workflow_runs"][0]
    if change in {"dry_run", "digital_twin"}:
        run["run_type"] = change
    elif change == "wrong_org":
        run["org_id"] = "different-org"
    elif change == "failed":
        run["status"] = "failed"
    elif change == "simulated":
        for step in client.evidence["workflow_steps"]:
            step["output_snapshot"]["simulated"] = True
    elif change == "missing_write_proof":
        for step in client.evidence["workflow_steps"]:
            step["output_snapshot"].pop("verification")
    else:
        client.evidence["workflow_steps"] = []
        evidence["freshservice"]["verified_actions"] = row["config"]["runtime_profiles"][0]["actions"]
    result = certify_asset(client, slug=row["slug"], actor_id="platform-1", runtime_evidence=evidence)
    assert result["certification"]["level"] == "governed"


@pytest.mark.parametrize("change", ["event_name_only", "missing_baseline", "no_sources", "wrong_play", "wrong_metric", "unverified", "wrong_org"])
def test_outcome_certification_rejects_unmeasured_or_unrelated_records(change):
    row = _asset(production_profile=True)
    client = _Client(row)
    evidence = {"orgId": ORG, "eventIds": [EVENT]}
    event = client.evidence["intelligence_outcome_events"][0]
    if change == "event_name_only":
        evidence = {"verified_outcome_events": ["ticket_sla_saved"]}
    elif change == "missing_baseline":
        event["before_value"] = None
    elif change == "no_sources":
        event["metadata"]["source_records"] = []
    elif change == "wrong_play":
        event["metadata"]["play_key"] = "unrelated"
    elif change == "wrong_metric":
        event["metadata"]["metric_key"] = "unrelated"
    elif change == "unverified":
        event["metadata"]["verified"] = False
    else:
        event["org_id"] = "different-org"
    result = certify_asset(client, slug=row["slug"], actor_id="platform-1", runtime_evidence=_runtime_evidence(row["config"]), outcome_evidence=evidence)
    assert result["certification"]["level"] == "production_verified"


def test_promotion_rechecks_persisted_proof():
    row = _asset(production_profile=True)
    client = _Client(row)
    certify_asset(client, slug=row["slug"], actor_id="platform-1", runtime_evidence=_runtime_evidence(row["config"]))
    client.evidence["workflow_runs"][0]["run_type"] = "dry_run"
    with pytest.raises(Marketplace3CertificationError, match="not evidence-linked"):
        promote_certified_asset(client, slug=row["slug"], actor_id="platform-1")
