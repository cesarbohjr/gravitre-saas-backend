#!/usr/bin/env python3
"""Run consolidated department eval suites (CI gate helper).

Examples:
  python scripts/run-department-eval-suite.py
  python scripts/run-department-eval-suite.py --department msp
  python scripts/run-department-eval-suite.py --manifest-only
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def _run_pytest(targets: list[str], *, quiet: bool, keyword: str | None = None) -> int:
    cmd = [sys.executable, "-m", "pytest", *targets]
    if quiet:
        cmd.append("-q")
    if keyword:
        cmd.extend(["-k", keyword])
    print("Running:", " ".join(cmd))
    return int(subprocess.run(cmd, cwd=str(BACKEND)).returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--department", help="Optional single department id")
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("-q", action="store_true", help="Quiet pytest")
    args = parser.parse_args()

    sys.path.insert(0, str(BACKEND))
    from app.services.department_eval_registry import (  # noqa: E402
        department_eval_manifest,
        get_department_eval_spec,
        list_department_eval_specs,
    )

    manifest = department_eval_manifest()
    if args.manifest_only:
        print(json.dumps(manifest, indent=2))
        return 0

    specs = list_department_eval_specs()
    if args.department:
        spec = get_department_eval_spec(args.department)
        if not spec:
            print(f"Unknown department: {args.department}", file=sys.stderr)
            return 2
        specs = [spec]

    # Consolidated suite: filter by department node-id when scoped.
    core_rc = _run_pytest(
        ["tests/eval/test_department_eval_suites.py"],
        quiet=args.q,
        keyword=args.department,
    )
    if core_rc != 0:
        return core_rc

    # Existing pack/vertical batteries for the selected departments (no -k —
    # legal/clio tests may not contain the department token in the node id).
    globs: list[str] = []
    for spec in specs:
        globs.extend(spec.pytest_globs)
    if not globs:
        return 0
    return _run_pytest(globs, quiet=args.q)


if __name__ == "__main__":
    raise SystemExit(main())
