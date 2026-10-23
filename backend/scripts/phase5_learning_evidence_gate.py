#!/usr/bin/env python3
"""Phase 5 evidence gate: run existing isolated contracts without claiming real-world learning.

This is a prerequisite suite, NOT a complete approved-action -> independent
provider readback -> verified measured outcome -> improved next turn experiment.
A missing/skip/failing test fails the gate. All results preserve provenance.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

CONTRACTS = {
    "approval_is_not_execution": [
        "tests/services/test_outcome_ownership_learning_contamination.py::test_approval_is_not_execution_success",
        "tests/services/test_outcome_ownership_learning_contamination.py::test_execution_success_does_not_create_positive_plan_bias",
    ],
    "measured_outcome_eligibility": [
        "tests/services/test_outcome_ownership_learning_contamination.py::test_measured_business_outcome_can_create_positive_bias",
        "tests/services/test_outcome_learning_handler.py::test_inconclusive_run_is_not_evidence_for_a_prediction",
        "tests/services/test_intelligence_outcome_path.py::test_unknown_steps_do_not_invent_dollar_impact",
    ],
    "tenant_scoping_and_retries": [
        "tests/services/test_outcome_learning_handler.py::test_org_scoping_never_crosses_orgs",
        "tests/services/test_outcome_learning_handler.py::test_transient_write_failure_raises_so_the_relay_retries",
        "tests/services/test_outcome_learning_handler.py::test_records_work_object_goal_predictions_and_play_learning_once",
    ],
    "repeat_turn_learning_prerequisites": [
        "tests/services/test_outcome_learning_handler.py::test_recommendation_ranking_reads_play_learning_only_when_enabled",
        "tests/services/test_outcome_learning_handler.py::test_labels_resolve_through_the_existing_labelling_job",
    ],
    "final_provider_write_gate": [
        "tests/services/pipecat_voice/test_phase3_provider_commit_gate.py",
    ],
}

def evaluate_xml(path: Path, expected_min: int) -> dict:
    evidence = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if not path.is_file():
        return evidence
    for case in ET.parse(path).iter("testcase"):
        evidence["tests"] += 1
        for kind in ("failure", "error", "skipped"):
            if case.find(kind) is not None:
                evidence[{"failure": "failures", "error": "errors", "skipped": "skipped"}[kind]] += 1
    evidence["complete"] = (
        evidence["tests"] >= expected_min
        and not any(evidence[k] for k in ("failures", "errors", "skipped"))
    )
    return evidence

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out = Path(os.environ.get("PHASE5_OUTPUT_DIR", root / "phase5-evidence"))
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for dimension, selectors in CONTRACTS.items():
        xml = out / (dimension + ".xml")
        cmd = [
            sys.executable, "-m", "pytest", "-q", "-p", "tests.offline_network_guard",
            "--disable-warnings", "--maxfail=1", "--junitxml", str(xml), *selectors,
        ]
        started = time.monotonic()
        try:
            run = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=180)
            code, stdout = run.returncode, run.stdout + "\n" + run.stderr
        except subprocess.TimeoutExpired as exc:
            code, stdout = 124, "Phase 5 contract timed out"
        (out / (dimension + ".log")).write_text(stdout[-30000:], encoding="utf-8")
        evidence = evaluate_xml(xml, len(selectors))
        results.append({
            "dimension": dimension,
            "status": "PASS_OFFLINE_PREREQUISITE" if code == 0 and evidence.get("complete", False) else "FAIL",
            "evidence_level": "mocked_or_isolated_contract",
            "tests": evidence,
            "exit_code": code,
            "harness_wall_seconds": round(time.monotonic() - started, 3),
            "selectors": selectors,
        })
        print(dimension, results[-1]["status"], flush=True)
    report = {
        "schema": "gravitre.phase5.evidence_gate.v1",
        "github_sha": os.environ.get("GITHUB_SHA", "unknown"),
        "results": results,
        "prerequisite_contracts_pass": all(x["status"] == "PASS_OFFLINE_PREREQUISITE" for x in results),
        "live_authorized_action_verified": False,
        "independent_provider_readback_verified": False,
        "independent_measured_business_outcome_verified": False,
        "repeat_turn_improvement_verified": False,
        "phase5_certification": "NOT_PROVEN",
        "disclosure": "Passing mocked contracts does not establish that a business outcome improved or that a model learned from real eligible data.",
    }
    (out / "phase5-evidence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["prerequisite_contracts_pass"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
