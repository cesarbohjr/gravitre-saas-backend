"""Resolve certification proof from persisted production execution records.

Request payloads identify records; they never attest to their own success.
"""
from __future__ import annotations

from math import isfinite
from typing import Any
from uuid import UUID

from app.connectors.action_catalog.registry import get_action_spec
from app.marketplace.schemas import OutcomePackAssetConfig


def _uuid(value: Any) -> str | None:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _rows(client: Any, table: str, org: str, ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    return client.table(table).select("*").eq("org_id", org).in_("id", ids).execute().data or []


def _production_runs(client: Any, org: str, ids: list[str]) -> list[dict[str, Any]]:
    return [row for row in _rows(client, "workflow_runs", org, ids)
            if row.get("run_type") == "execute"
            and row.get("environment") == "production"
            and row.get("status") == "completed" and row.get("completed_at")]


def resolve_runtime_evidence(client: Any, config: OutcomePackAssetConfig, evidence: dict[str, Any]) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    # Runner diagnostics do not participate in live certification.
    if isinstance(evidence.get("runner"), dict):
        resolved["runner"] = evidence["runner"]
    for profile in config.runtime_profiles:
        claim = evidence.get(profile.provider)
        if not isinstance(claim, dict):
            continue
        org = _uuid(claim.get("orgId"))
        ids = [_uuid(value) for value in claim.get("runIds", [])] if isinstance(claim.get("runIds"), list) else []
        ids = list(dict.fromkeys(value for value in ids if value))[:100]
        if not org or not ids:
            continue
        runs = _production_runs(client, org, ids)
        verified: set[str] = set()
        accepted_runs: list[str] = []
        for run in runs:
            steps = client.table("workflow_steps").select("*").eq("org_id", org).eq("run_id", run["id"]).execute().data or []
            for step in steps:
                snap = step.get("output_snapshot") or {}
                if not isinstance(snap, dict) or step.get("status") != "completed" or snap.get("success") is not True:
                    continue
                structured = snap.get("structured") or {}
                if snap.get("simulated") is True or snap.get("predicted") is True or (isinstance(structured, dict) and structured.get("simulated") is True):
                    continue
                action = str(snap.get("invoke_action") or snap.get("action") or "")
                spec = get_action_spec(action)
                if action not in profile.actions or not spec:
                    continue
                if spec.kind != "read":
                    proof = snap.get("verification") or {}
                    verified_write = isinstance(proof, dict) and proof.get("verified") is True and proof.get("status") == "verified"
                    # Canonical synchronous source-of-record verifier snapshots.
                    for key in ("population_verify", "field_assert_verify", "entity_get_verify"):
                        proof = snap.get(key) or {}
                        verified_write = verified_write or (isinstance(proof, dict) and proof.get("verified") is True)
                    if not verified_write:
                        continue
                verified.add(action)
                accepted_runs.append(str(run["id"]))
        if verified:
            resolved[profile.provider] = {
                "environment": "production", "orgId": org,
                "runIds": list(dict.fromkeys(accepted_runs)),
                "evidence_ref": "workflow_runs:" + ",".join(dict.fromkeys(accepted_runs)),
                "verified_actions": sorted(verified),
            }
    return resolved


def measured_outcome_valid(row: dict[str, Any]) -> bool:
    def number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
    refs = row.get("sourceRecords")
    return bool(row.get("evidenceId") and row.get("orgId") and row.get("runId")
                and row.get("measuredAt") and row.get("verificationMethod")
                and row.get("metricKey") and row.get("playKey") and row.get("outcomeEvent")
                and number(row.get("baselineValue")) and number(row.get("resultValue"))
                and isinstance(refs, list) and refs
                and all(isinstance(ref, dict) and all(ref.get(key) for key in ("system", "record_type", "record_id")) for ref in refs))


def resolve_outcome_evidence(client: Any, config: OutcomePackAssetConfig, evidence: dict[str, Any]) -> dict[str, Any]:
    org = _uuid(evidence.get("orgId"))
    ids = [_uuid(value) for value in evidence.get("eventIds", [])] if isinstance(evidence.get("eventIds"), list) else []
    ids = list(dict.fromkeys(value for value in ids if value))[:100]
    if not org or not ids:
        return {}
    plays = {play.key: play for play in config.plays}
    measured = []
    for row in _rows(client, "intelligence_outcome_events", org, ids):
        meta = row.get("metadata") or {}
        if not isinstance(meta, dict):
            continue
        play = plays.get(meta.get("play_key"))
        if (not play or row.get("outcome_event") != "play_business_result"
                or row.get("measurement_status") != "recorded"
                or meta.get("contract") != "play_business_result/v1"
                or meta.get("verification_state") != "VERIFIED SUCCESS" or meta.get("verified") is not True
                or meta.get("outcome_type") not in play.outcome_events
                or meta.get("metric_key") not in play.kpi_keys):
            continue
        run_id = _uuid(row.get("workflow_run_id"))
        if not run_id or not _production_runs(client, org, [run_id]):
            continue
        value = {"evidenceId": str(row["id"]), "orgId": org, "runId": run_id,
                 "outcomeEvent": meta.get("outcome_type"), "playKey": play.key,
                 "metricKey": meta.get("metric_key"), "baselineValue": row.get("before_value"),
                 "resultValue": row.get("after_value"), "sourceRecords": meta.get("source_records"),
                 "verificationMethod": meta.get("verification_method"), "measuredAt": row.get("measured_at")}
        if measured_outcome_valid(value):
            measured.append(value)
    return {"orgId": org, "eventIds": [value["evidenceId"] for value in measured], "measurements": measured}
