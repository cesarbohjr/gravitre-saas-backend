#!/usr/bin/env python3
"""Local Release 2/3 engineering gate — unit tests only (not production acceptance)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
OUT = ROOT / "docs/delivery/release-engineering-gates.json"

TESTS = [
    "tests/services/test_workflow_approval_scope.py",
    "tests/services/test_canvas_write_approval_scope.py",
    "tests/services/test_write_invoke_idempotency.py",
    "tests/services/test_lifecycle_envelope.py",
    "tests/services/test_event_trigger_queue.py",
    "tests/services/test_event_triggered_runs.py",
    "tests/services/test_write_authority_spine.py",
    "tests/services/test_msp_org_context.py",
    "tests/services/test_automation_actor.py",
]


def main() -> int:
    cmd = [sys.executable, "-m", "pytest", *TESTS, "-q", "--tb=line"]
    proc = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True)
    report = {
        "verdict": "PASS" if proc.returncode == 0 else "FAIL",
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-2000:],
        "tests": TESTS,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT), "verdict": report["verdict"]}, indent=2))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
