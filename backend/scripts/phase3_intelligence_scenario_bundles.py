#!/usr/bin/env python3
"""Three reproducible Phase 3 scenario *contract bundles* using real repository tests.

These are offline integration slices, NOT a simulated full business journey,
real connector execution, or seven-layer end-to-end certification.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

SCENARIOS = {
    "customer_support": [
        "tests/services/test_phase2_intelligence_coordination.py::test_shared_decision_contains_all_seven_and_reuses_perception_and_graph",
        "tests/services/test_phase2_router_consumers.py::test_temporal_absence_and_disabled_sentiment_are_not_available_claims",
        "tests/services/test_phase2_intelligence_coordination.py::test_optional_failures_are_visible_and_do_not_discard_other_capabilities",
        "tests/services/test_phase2_intelligence_coordination.py::test_evidence_is_bounded_fenced_and_cannot_inject_extra_capability",
    ],
    "sales_operations": [
        "tests/services/test_phase2_router_consumers.py::test_relational_resolution_reuses_scoped_known_nodes_without_extra_model_call",
        "tests/services/test_phase2_router_consumers.py::test_unmatched_entity_stays_unknown_without_guessed_identifier",
        "tests/services/test_intelligence_outcome_path.py::test_outcome_path_has_full_chain_and_unknown_gaps",
        "tests/services/test_phase2_intelligence_coordination.py::test_shared_decision_contains_all_seven_and_reuses_perception_and_graph",
    ],
    "it_incident_management": [
        "tests/services/test_phase2_intelligence_coordination.py::test_optional_failures_are_visible_and_do_not_discard_other_capabilities",
        "tests/services/test_phase2_router_consumers.py::test_deferred_turn_never_starts_any_optional_provider_even_with_classification_flags",
        "tests/services/test_phase2_intelligence_coordination.py::test_shared_decision_contains_all_seven_and_reuses_perception_and_graph",
        "tests/services/test_phase2_intelligence_coordination.py::test_evidence_is_bounded_fenced_and_cannot_inject_extra_capability",
    ],
}

def main():
    root = Path(__file__).resolve().parents[1]
    output = Path(os.environ.get("PHASE3_SCENARIO_OUTPUT", str(root / "phase3-evidence" / "scenario-bundles")))
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for name, selectors in SCENARIOS.items():
        junit = output / (name + ".xml")
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "tests.offline_network_guard",
               "--disable-warnings", "--maxfail=1", "--junitxml", str(junit), *selectors]
        start = time.monotonic()
        try:
            run = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=180)
            code, logs = run.returncode, run.stdout + "\n" + run.stderr
        except subprocess.TimeoutExpired:
            code, logs = 124, "Scenario contract bundle timed out"
        (output / (name + ".log")).write_text(logs[-30000:])
        count, failures = 0, 0
        if junit.exists():
            for case in ET.parse(junit).iter("testcase"):
                count += 1
                if case.find("failure") is not None or case.find("error") is not None or case.find("skipped") is not None:
                    failures += 1
        passed = code == 0 and count >= len(selectors) and failures == 0
        results.append({"scenario": name, "status": "PASS_OFFLINE_CONTRACT_BUNDLE" if passed else "FAIL",
                        "evidence_level": "existing_mocked_repository_tests",
                        "full_business_journey_verified": False, "seven_layer_cross_surface_certified": False,
                        "provider_readback_verified": False, "tests_run": count, "failures_or_skips": failures,
                        "exit_code": code, "elapsed_seconds": round(time.monotonic() - start, 3),
                        "selectors": selectors})
        print(name, results[-1]["status"], flush=True)
    report = {"schema": "gravitre.phase3.scenario_bundles.v1",
              "certification": "NOT_CERTIFIED", "scenarios": results}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if all(row["status"] == "PASS_OFFLINE_CONTRACT_BUNDLE" for row in results) else 1

if __name__ == "__main__":
    raise SystemExit(main())
