"""ECO-001 consolidated, fail-closed acceptance runner.

Run from backend/ with PostgreSQL binaries installed. Does not touch production,
deploy, merge, or perform real provider writes. An isolated acceptance Supabase
project is a separate explicitly authorized gate, not silently invoked here.
"""
from __future__ import annotations

import os
import subprocess
import sys
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
    command = [sys.executable, "-m", "pytest", "-q", "-ra", "--strict-markers", *SUITES]
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if result.returncode:
        print(f"ECO-001 NOT CERTIFIED: suite failed ({result.returncode})", file=sys.stderr)
        return result.returncode
    # A green local suite is a prerequisite, not exact-head CI or live
    # acceptance infrastructure certification.
    print("ECO-001 local acceptance suite passed; exact-head CI and isolated QA "
          "provider/ledger acceptance are still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
