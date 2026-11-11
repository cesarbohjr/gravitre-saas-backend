"""ECO-001 consolidated, fail-closed acceptance runner.

Run from backend/ with PostgreSQL binaries installed. Does not touch production,
deploy, merge, or perform real provider writes. An isolated acceptance Supabase
project is a separate explicitly authorized gate, not silently invoked here.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = (
    "tests/routers/test_eco001_chat_execute_ingress.py",
    "tests/services/test_eco001_inflight_chat_cancellation.py",
    "tests/services/test_autonomous_invoke_receiver_integration.py",
    "tests/services/test_write_invoke_idempotency.py",
    "tests/db/test_write_invoke_idempotency_pg.py",
    "tests/db/test_autonomous_independent_write_pg.py",
    "tests/master_qa/test_joined_agent_play_approval_step_pg.py",
)


def main() -> int:
    # Direct script execution sets sys.path[0] to backend/scripts, not backend.
    # Match `python -m pytest` import semantics before loading the PG harness.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.db.pg_harness import PG_BIN

    if PG_BIN is None:
        print("ECO-001 NOT CERTIFIED: PostgreSQL server binaries unavailable", file=sys.stderr)
        return 2
    missing = [name for name in SUITES if not (ROOT / name).is_file()]
    if missing:
        print(f"ECO-001 NOT CERTIFIED: missing test suites: {missing}", file=sys.stderr)
        return 2
    env = os.environ.copy()
    env["GRAVITRE_REQUIRE_PG"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="eco001-acceptance-") as output:
        report = Path(output) / "junit.xml"
        command = [sys.executable, "-m", "pytest", "-q", "-ra", "--strict-markers",
                   f"--junitxml={report}", *SUITES]
        result = subprocess.run(command, cwd=ROOT, env=env, check=False)
        if result.returncode:
            print(f"ECO-001 NOT CERTIFIED: suite failed ({result.returncode})", file=sys.stderr)
            return result.returncode
        if not report.is_file():
            print("ECO-001 NOT CERTIFIED: pytest produced no JUnit report", file=sys.stderr)
            return 2
        try:
            root = ET.parse(report).getroot()
            cases = root.findall(".//testcase")
            skipped = [case for case in cases if case.find("skipped") is not None]
            failed = [case for case in cases if case.find("failure") is not None
                      or case.find("error") is not None]
        except ET.ParseError as exc:
            print(f"ECO-001 NOT CERTIFIED: invalid JUnit report: {exc}", file=sys.stderr)
            return 2
        if not cases or skipped or failed:
            print(f"ECO-001 NOT CERTIFIED: cases={len(cases)}, "
                  f"skipped={len(skipped)}, failed={len(failed)}", file=sys.stderr)
            return 2
    # A green local suite is a prerequisite, not exact-head CI or live
    # acceptance infrastructure certification.
    print("ECO-001 local acceptance suite passed; exact-head CI and isolated QA "
          "provider/ledger acceptance are still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
