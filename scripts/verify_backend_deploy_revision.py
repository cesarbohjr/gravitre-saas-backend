#!/usr/bin/env python3
"""Verify health SHA against the target, allowing only runtime-equivalent ancestors."""
from __future__ import annotations

import argparse
import json
import re
import subprocess

from railway_commit_touches_backend import commit_range_touches_backend


def _resolve_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{8,40}", value):
        raise ValueError("Revision must be a hexadecimal commit SHA")
    return subprocess.check_output(["git", "rev-parse", "--verify", f"{value}^{{commit}}"], text=True).strip()


def verify_revision(reported: str, expected: str) -> tuple[bool, str]:
    try:
        deployed, target = _resolve_sha(reported), _resolve_sha(expected)
        if deployed == target:
            return True, "exact_commit"
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", deployed, target], check=False)
        if ancestor.returncode != 0:
            return False, "not_target_ancestor"
        changed, _ = commit_range_touches_backend(deployed, target)
        return (False, "backend_runtime_changed") if changed else (True, "runtime_equivalent_ancestor")
    except (ValueError, subprocess.CalledProcessError, RuntimeError):
        return False, "unresolvable_revision"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health-json", required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        with open(args.health_json, encoding="utf-8") as file:
            reported = str(json.load(file).get("git_sha") or "").strip()
        ok, reason = verify_revision(reported, args.expected_sha)
    except (OSError, ValueError, AttributeError):
        ok, reason = False, "invalid_health_json"
    print(json.dumps({"backend_revision_verified": ok, "reason": reason}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
