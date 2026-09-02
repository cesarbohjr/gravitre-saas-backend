#!/usr/bin/env python3
"""Before/after live proof for instance 2, without ever regressing production.

Runs the real Anthropic tool-carrying unified turn twice:

  pre-fix   the two source files reverted to 3a4cd5f3 (the commit before the
            first fix), where the payload conversion strips the marker
            -> expect BUG_REPRODUCED at provider_tool_router.complete_with_tools
  post-fix  the working tree as committed
            -> expect CLEAN

Both runs are local processes against real prod credentials, the real Anthropic
API and the isolated conversation org -- the same evidence route this program
already accepted for `smoke-multi-provider-tool-live.py`. Production is never
served the pre-fix code, so there is no regression window.

The source files are restored in a finally block, and the script refuses to
start if the working tree is dirty, so an interrupted run cannot leave reverted
code behind.

    python scripts/prove-unnarrowed-nonopenai-beforeafter.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PRE_FIX_SHA = "3a4cd5f3"
FILES = [
    "backend/app/services/narrowed_tools.py",
    "backend/app/services/unified_turn_reasoning_service.py",
]
PROBE = "scripts/probe-unnarrowed-nonopenai-live.py"
OUT = REPO / "docs" / "delivery" / "unnarrowed-nonopenai-live.json"


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=False
    )


def dirty() -> list[str]:
    out = git("status", "--porcelain", "--", *FILES).stdout.strip()
    return [ln for ln in out.splitlines() if ln.strip()]


def run_probe(label: str) -> int:
    print(f"\n{'=' * 62}\n  {label}\n{'=' * 62}")
    proc = subprocess.run(
        [sys.executable, PROBE, "--label", label], cwd=REPO, text=True
    )
    return proc.returncode


def verdicts() -> dict[str, str]:
    if not OUT.is_file():
        return {}
    try:
        rows = json.loads(OUT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(rows, dict):
        rows = [rows]
    return {str(r.get("label")): str(r.get("verdict")) for r in rows}


def main() -> int:
    if dirty():
        print("working tree is dirty for the files this script reverts:")
        for line in dirty():
            print(" ", line)
        print("commit or stash first; refusing to run")
        return 1

    run_probe("post-fix")

    print(f"\nreverting {len(FILES)} files to {PRE_FIX_SHA} (local only)...")
    revert = git("checkout", PRE_FIX_SHA, "--", *FILES)
    if revert.returncode != 0:
        print("revert failed:", revert.stderr.strip())
        return 1
    try:
        run_probe("pre-fix")
    finally:
        print("\nrestoring files to HEAD...")
        git("checkout", "HEAD", "--", *FILES)
        still = dirty()
        print("restored clean" if not still else f"WARNING dirty: {still}")

    found = verdicts()
    pre = found.get("pre-fix", "?")
    post = found.get("post-fix", "?")
    print(f"\n{'=' * 62}")
    print(f"  pre-fix  : {pre}   (want BUG_REPRODUCED)")
    print(f"  post-fix : {post}   (want CLEAN)")
    ok = pre == "BUG_REPRODUCED" and post == "CLEAN"
    print(f"  RESULT   : {'PASS' if ok else 'NOT PROVEN'}")
    print(f"{'=' * 62}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
