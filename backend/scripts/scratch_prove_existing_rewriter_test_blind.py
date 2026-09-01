"""Demonstrate that the pre-existing query_rewriter test could never catch this bug.

`test_query_rewriter_uses_conversation_context` patches the factory with
`patch(..., return_value=router)`, which installs a MagicMock. A MagicMock
accepts ANY signature, so `get_model_router(settings)` succeeds inside the test
while the real zero-arg factory raises TypeError in production.

The test therefore passes identically with the bug present and absent. Rather
than assert that, run it both ways and show it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SRC = BACKEND / "app" / "services" / "query_rewriter.py"
TEST = "tests/test_intelligence_engine_gaps.py::test_query_rewriter_uses_conversation_context"

FIXED = "        router = get_model_router()"
BUGGY = "        router = get_model_router(settings)"


def run() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-q", "--no-header"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def main() -> int:
    original = SRC.read_text(encoding="utf-8")
    if FIXED not in original:
        print("fix not applied; nothing to demonstrate")
        return 1

    try:
        with_fix = run()
        SRC.write_text(original.replace(FIXED, BUGGY, 1), encoding="utf-8")
        with_bug = run()
    finally:
        SRC.write_text(original, encoding="utf-8")

    print(f"  existing test WITH the fix : {'PASS' if with_fix else 'FAIL'}")
    print(f"  existing test WITH the bug : {'PASS' if with_bug else 'FAIL'}")

    if with_fix and with_bug:
        print(
            "\nCONFIRMED BLIND — the existing test passes either way, so it was never\n"
            "capable of catching the dormancy. Its MagicMock accepts an argument the\n"
            "real factory rejects, which is the mock encoding a contract the\n"
            "production code does not have."
        )
        return 0
    print("\nthe existing test does discriminate — the concern does not apply")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
