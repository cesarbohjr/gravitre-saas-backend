#!/usr/bin/env python3
"""Phase 3 coverage inventory gate. Inventory is NOT integration certification."""
import argparse
import json
import hashlib
import os
from pathlib import Path

CAPABILITIES = ("contextual", "sentiment", "causal", "temporal", "relational", "adaptive", "predictive")
SURFACES = ("flows", "plays", "agents", "workflows", "connectors", "knowledge", "memory", "governance")
SCENARIOS = ("customer_support", "sales_operations", "it_incident_management")

def build(evidence_dir=None, commit_sha=None, differential_evidence=None):
    report = {
        "schema": "gravitre.phase3.intelligence_coverage.v1",
        "certification": "NOT_CERTIFIED",
        "scenario_ids": list(SCENARIOS),
        "cells": [
            {"id": f"{capability}:{surface}", "capability": capability, "surface": surface,
             "status": "NOT_TESTED", "test_selector": None, "evidence_artifact": None}
            for capability in CAPABILITIES for surface in SURFACES
        ],
    }
    if evidence_dir is None:
        return report
    if not commit_sha:
        raise ValueError("Evidence ingestion requires an explicit commit SHA")
    report["commit_sha"] = commit_sha
    records = {}
    for path in sorted(Path(evidence_dir).glob("*.json")):
        record = json.loads(path.read_text())
        identity = (record.get("cell_id"), record.get("scenario_id"))
        if identity in records:
            raise ValueError("Duplicate cell/scenario evidence: " + str(identity))
        if identity[0] not in {c["id"] for c in report["cells"]} or identity[1] not in SCENARIOS:
            raise ValueError("Unknown evidence cell/scenario: " + str(identity))
        if record.get("commit_sha") != commit_sha:
            raise ValueError("Stale or foreign-commit evidence: " + path.name)
        if not record.get("test_selector") or not isinstance(record.get("seed"), int):
            raise ValueError("Evidence requires test selector and deterministic seed")
        if record.get("observed") != record.get("expected") or record.get("expected") is None:
            raise ValueError("Observed behavior does not match expected behavior")
        writes = record.get("writes_committed")
        attempts = record.get("write_attempts")
        if type(writes) is not int or type(attempts) is not int or not 0 <= writes <= attempts:
            raise ValueError("Invalid write counters")
        if writes and record.get("approval_state") != "granted":
            raise ValueError("Unauthorized write in certification evidence")
        if record.get("status") not in ("PASS_OFFLINE_CONTRACT", "PASS_LIVE_VERIFIED", "FAIL"):
            raise ValueError("Unknown test evidence status")
        if record["status"] == "PASS_LIVE_VERIFIED":
            readback = record.get("provider_readback")
            if (record.get("evidence_scope") != "live_provider_integration"
                    or not isinstance(readback, dict)
                    or readback.get("independent") is not True
                    or readback.get("verified") is not True
                    or not readback.get("source_record_id")
                    or not readback.get("request_id")):
                raise ValueError("Live certification requires independent provider readback")
        records[identity] = (record, path)
    for cell in report["cells"]:
        selected = [records.get((cell["id"], scenario)) for scenario in SCENARIOS]
        present = [item for item in selected if item is not None]
        cell["scenario_evidence"] = [
            {"scenario_id": row["scenario_id"], "test_selector": row["test_selector"],
             "evidence_artifact": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for row, path in present]
        if len(present) != len(SCENARIOS):
            continue
        statuses = {row["status"] for row, _ in present}
        cell["status"] = ("FAIL" if "FAIL" in statuses else "PASS_LIVE_VERIFIED"
                          if statuses == {"PASS_LIVE_VERIFIED"} else "PASS_OFFLINE_CONTRACT")
        cell["test_selector"] = [row["test_selector"] for row, _ in present]
        cell["evidence_artifact"] = [str(path) for _, path in present]
    # Full certification is deliberately not inferred from boundary propagation.
    # Differential business-decision evidence is a separate mandatory gate.
    report["differential_certification"] = "NOT_PROVEN"
    if differential_evidence is not None:
        differential = json.loads(Path(differential_evidence).read_text())
        if differential.get("commit_sha") != commit_sha:
            raise ValueError("Differential evidence belongs to another commit")
        cases = differential.get("cases", [])
        expected_cases = {(s, c) for s in SCENARIOS for c in CAPABILITIES}
        identities = [(c.get("scenario_id"), c.get("capability")) for c in cases]
        if len(identities) != 21 or set(identities) != expected_cases:
            raise ValueError("Expected 21 unique differential scenario/capability cases")
        for case in cases:
            if (case.get("commit_sha") != commit_sha or case.get("status") != "PASS_LIVE_DECISION"
                    or not case.get("request_id") or not case.get("response_id") or not case.get("model")
                    or case.get("evidence_scope") != "live_model_synthetic_sources"):
                raise ValueError("Differential case has no passing live-model provenance")
            observed = case.get("observed", {})
            expected_decisions = {"baseline": "routine", "enriched": "urgent_review", "missing": "uncertain"}
            if set(observed) != set(expected_decisions):
                raise ValueError("Missing differential decision variants")
            for variant, priority in expected_decisions.items():
                decision = observed[variant]
                if (decision.get("priority") != priority or decision.get("approval_granted") is not False
                        or type(decision.get("writes_committed")) is not int or decision["writes_committed"] != 0
                        or decision.get("causation_established") is not False
                        or decision.get("business_outcome_verified") is not False):
                    raise ValueError("Differential decision or governance assertion failed")
        report["differential_certification"] = "LIVE_MODEL_VERIFIED_SYNTHETIC_SOURCES"
        report["differential_evidence_artifact"] = str(differential_evidence)
    if (all(c["status"] == "PASS_LIVE_VERIFIED" for c in report["cells"])
            and report["differential_certification"] == "LIVE_MODEL_VERIFIED_SYNTHETIC_SOURCES"):
        report["certification"] = "CERTIFIED"
    return report

def validate(payload):
    cells = payload.get("cells", [])
    expected = {f"{c}:{s}" for c in CAPABILITIES for s in SURFACES}
    ids = [c.get("id") for c in cells]
    if len(ids) != 56 or len(set(ids)) != 56 or set(ids) != expected:
        raise ValueError("Expected exactly 56 unique capability/surface cells")
    if payload.get("scenario_ids") != list(SCENARIOS):
        raise ValueError("Three mandatory scenario IDs are missing or reordered")
    for cell in cells:
        if cell["status"] not in ("NOT_TESTED", "PASS_OFFLINE_CONTRACT", "FAIL", "PASS_LIVE_VERIFIED"):
            raise ValueError("Unknown coverage status: " + str(cell["status"]))
        if cell["status"].startswith("PASS") and not (cell.get("test_selector") and cell.get("evidence_artifact")):
            raise ValueError("PASS requires test selector and evidence artifact: " + cell["id"])
    if payload.get("certification") == "CERTIFIED" and any(c["status"] != "PASS_LIVE_VERIFIED" for c in cells):
        raise ValueError("Cannot certify incomplete or offline-only coverage")
    if payload.get("certification") == "CERTIFIED" and payload.get("differential_certification") != "LIVE_MODEL_VERIFIED_SYNTHETIC_SOURCES":
        raise ValueError("Cannot certify without differential decision evidence")
    return {"total": len(cells), "not_tested": sum(c["status"] == "NOT_TESTED" for c in cells),
            "offline_pass": sum(c["status"] == "PASS_OFFLINE_CONTRACT" for c in cells),
            "live_verified": sum(c["status"] == "PASS_LIVE_VERIFIED" for c in cells)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="phase3-evidence/intelligence-coverage.json")
    parser.add_argument("--require-certified", action="store_true")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--commit-sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--differential-evidence")
    args = parser.parse_args()
    report = build(args.evidence_dir, args.commit_sha, args.differential_evidence)
    stats = validate(report)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({**report, "summary": stats}, indent=2) + "\n")
    print(json.dumps({"certification": report["certification"], **stats}))
    return 1 if args.require_certified and report["certification"] != "CERTIFIED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
