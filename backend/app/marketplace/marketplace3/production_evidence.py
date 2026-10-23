"""Read-only, configuration-bound certification proof from canonical run ledgers.

Caller-provided booleans, runtime profile labels and fixture runs are never proof.
Missing ledger dimensions deliberately prevent production certification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from math import isfinite

from app.core.safe_dict import safe_normalize_stored_dict
from app.services.outcome_verification import evidence_is_verified

REQUIRED_CHECKS = (
    "fresh_install_passed", "golden_path_passed", "failure_path_passed",
    "permissions_passed", "kpi_reconciliation_passed", "source_of_record_verification_passed",
)


@dataclass(frozen=True)
class ProductionEvidence:
    """Server-collected evidence, never deserialized from an API request."""
    org_id: str
    asset_id: str
    config_digest: str
    actions: frozenset[str] = frozenset()
    checks: dict[str, bool] = field(default_factory=dict)
    run_ids: tuple[str, ...] = ()
    measured_outcome_events: frozenset[str] = frozenset()

    def covers(self, actions: set[str]) -> bool:
        return bool(actions) and actions <= self.actions and all(self.checks.get(k) is True for k in REQUIRED_CHECKS)

    def as_dict(self) -> dict[str, Any]:
        return {"source": "canonical_production_ledgers", "org_id": self.org_id,
                "asset_id": self.asset_id, "config_digest": self.config_digest,
                "verified_actions": sorted(self.actions), "checks": self.checks,
                "run_ids": list(self.run_ids), "verified_outcome_events": sorted(self.measured_outcome_events)}


def collect_production_evidence(client: Any, *, org_id: str, asset_id: str, config_digest: str, config: Any = None) -> ProductionEvidence:
    """Require exact pack/digest provenance and fresh attributable read-back.

    The canonical workflow recorder must stamp certification context on runs;
    arbitrary existing runs from the same organization cannot certify a pack.
    A partial/truncated query can only withhold proof, never manufacture it.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (client.table("workflow_runs").select("id,org_id,status,environment,parameters,created_at")
            .eq("org_id", org_id).eq("environment", "production")
            .gte("created_at", cutoff.isoformat()).limit(1000).execute().data or [])
    actions: set[str] = set()
    refs: list[str] = []
    for row in rows:
        params = safe_normalize_stored_dict(row.get("parameters"))
        provenance = safe_normalize_stored_dict(params.get("marketplace_certification"))
        if (str(row.get("org_id")) != org_id or row.get("environment") != "production"
                or provenance.get("asset_id") != asset_id or provenance.get("config_digest") != config_digest
                or provenance.get("fixture") is not False or row.get("status") != "completed"):
            continue
        try:
            stamp = datetime.fromisoformat(str(row.get("created_at")).replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp < cutoff or stamp > datetime.now(timezone.utc):
                continue
        except (TypeError, ValueError):
            continue
        action = str(params.get("invoke_action") or "").strip()
        proof = safe_normalize_stored_dict(params.get("verification"))
        if not action or not row.get("id") or not evidence_is_verified(proof):
            continue
        if proof.get("action") != action or not (proof.get("resource_id") or proof.get("entity_id")):
            continue
        actions.add(action)
        refs.append(str(row["id"]))
    # Scenario receipts are append-only service-owned evidence. They are not
    # accepted from the caller's evidence dict, asset tags, or run parameters.
    check_rows = (client.table("marketplace_outcome_pack_checks")
        .select("org_id,asset_id,config_digest,check_kind,environment,passed,evidence_ref,checked_at")
        .eq("org_id", org_id).eq("asset_id", asset_id).eq("config_digest", config_digest)
        .eq("environment", "production").gte("checked_at", cutoff.isoformat())
        .order("checked_at", desc=True).limit(1000).execute().data or [])
    checks: dict[str, bool] = {}
    for row in check_rows:
        kind = row.get("check_kind")
        if kind not in REQUIRED_CHECKS or kind in checks:
            continue
        if (row.get("org_id") != org_id or row.get("asset_id") != asset_id
                or row.get("config_digest") != config_digest or row.get("environment") != "production"):
            continue
        try:
            stamp = datetime.fromisoformat(str(row.get("checked_at")).replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp < cutoff or stamp > datetime.now(timezone.utc):
                continue
        except (TypeError, ValueError):
            continue
        checks[kind] = row.get("passed") is True and bool(str(row.get("evidence_ref") or "").strip())
    measured_events: set[str] = set()
    if refs and config is not None:
        plays = {play.key: play for play in config.plays}
        results = (client.table("intelligence_outcome_events")
            .select("org_id,workflow_run_id,measurement_status,before_value,after_value,metadata,measured_at")
            .eq("org_id", org_id).eq("outcome_event", "play_business_result")
            .eq("measurement_status", "recorded").in_("workflow_run_id", refs)
            .gte("measured_at", cutoff.isoformat()).limit(1000).execute().data or [])
        for row in results:
            meta = safe_normalize_stored_dict(row.get("metadata"))
            play = plays.get(str(meta.get("play_key") or ""))
            if (row.get("org_id") != org_id or str(row.get("workflow_run_id")) not in refs
                    or row.get("measurement_status") != "recorded" or play is None
                    or meta.get("contract") != "play_business_result/v1" or meta.get("verified") is not True
                    or meta.get("verification_state") != "VERIFIED SUCCESS" or not meta.get("verification_method")
                    or not meta.get("source_records") or not meta.get("evidence_ids")
                    or meta.get("metric_key") not in play.kpi_keys):
                continue
            try:
                stamp = datetime.fromisoformat(str(row.get("measured_at")).replace("Z", "+00:00"))
                if stamp.tzinfo is None or stamp < cutoff or stamp > datetime.now(timezone.utc):
                    continue
                if not all(isfinite(float(row[key])) for key in ("before_value", "after_value")):
                    continue
            except (TypeError, ValueError, KeyError):
                continue
            measured_events.update(play.outcome_events)
    return ProductionEvidence(org_id, asset_id, config_digest, frozenset(actions), checks, tuple(refs), frozenset(measured_events))
