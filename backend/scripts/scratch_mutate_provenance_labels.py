"""Mutation-test the two provenance-label guards added 2026-08-31.

The bug they exist for is a label collapse, not a missing value, so a test that
only checks "provenance is present" passes either way. Each mutation below
restores the old, wrong behaviour in the shipped data file and the named test
must fail. Data file is restored afterwards.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "app" / "connectors" / "action_catalog" / "data" / "api_reference_map.json"
sys.stdout.reconfigure(encoding="utf-8")


def run(test: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", f"tests/test_api_reference_map.py::{test}", "-q"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip().splitlines()[-1]


def relabel_no_endpoint(actions: dict) -> str:
    hits = [k for k, v in actions.items() if v.get("provenance") == "no_vendor_endpoint"]
    for k in hits:
        actions[k]["provenance"] = "manual_verified"
    return f"relabelled {len(hits)} no_vendor_endpoint entries back to manual_verified"


def flatten_multi(actions: dict) -> str:
    hits = [k for k, v in actions.items() if v.get("provenance") == "dedicated_multi"]
    for k in hits:
        actions[k]["provenance"] = "dedicated"
    return f"flattened {len(hits)} dedicated_multi entries to dedicated"


MUTATIONS = [
    ("test_no_endpoint_actions_are_not_labelled_as_hand_verified_routes", relabel_no_endpoint),
    ("test_multi_endpoint_actions_keep_their_own_provenance", flatten_multi),
]


def main() -> int:
    original = DATA.read_text(encoding="utf-8")
    results = []
    try:
        for test, mutate in MUTATIONS:
            payload = json.loads(original)
            description = mutate(payload["actions"])
            DATA.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            code, last = run(test)
            results.append((test, description, code, last))
    finally:
        DATA.write_text(original, encoding="utf-8")

    all_caught = True
    for test, description, code, last in results:
        caught = code != 0
        all_caught &= caught
        print(f"{'CAUGHT ' if caught else 'MISSED '} {test}")
        print(f"           mutation: {description}")
        print(f"           pytest  : {last}")

    code, last = run("test_no_endpoint_actions_are_not_labelled_as_hand_verified_routes")
    print(f"\nrestored data file, guard passes again: {code == 0} ({last})")
    print(f"\nall mutations caught: {all_caught}")
    return 0 if all_caught and code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
