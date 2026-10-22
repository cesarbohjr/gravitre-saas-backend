#!/usr/bin/env python3
"""Fail offline voice acceptance when any graded replay scenario misses its expected outcome.

The replay must exercise the production begin_write_effect gate, including
voice pause enforcement, as corrected in PR #536 on the merged base.
"""
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
failed = []
for scenario_id, scenario in report["scenarios"].items():
    accuracy = scenario["aggregate"].get("accuracy") or {}
    n, passed = accuracy.get("n", 0), accuracy.get("pass", 0)
    if scenario.get("graded") and n and passed != n:
        failed.append(f'{scenario_id}: {passed}/{n} passing; outcomes={scenario["aggregate"].get("outcomes")}')
if failed:
    print("PHASE 3 VOICE REPLAY FAIL:\n" + "\n".join(failed))
    sys.exit(1)
print("PHASE 3 VOICE REPLAY PASS: all graded scenarios passed")
