"""Break the api_reference map four ways and confirm the tests catch each.

A passing suite proves nothing unless the suite fails when the thing it guards
is actually broken. Each mutation is applied to the shipped data file, pytest is
run, and the file is restored.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "app" / "connectors" / "action_catalog" / "data" / "api_reference_map.json"
sys.stdout.reconfigure(encoding="utf-8")

ORIGINAL = DATA.read_text(encoding="utf-8")


def drop_an_action(payload: dict) -> str:
    del payload["actions"]["hubspot.contacts.get"]
    return "delete a mapped action (simulates a new action never being mapped)"


def strip_provenance(payload: dict) -> str:
    payload["actions"]["asana.tasks.create"].pop("provenance", None)
    return "serve an endpoint with no provenance"


def silence_a_no_endpoint_action(payload: dict) -> str:
    payload["actions"]["email.send"].pop("note", None)
    return "drop the reason an action has no endpoint"


def fake_vendor_validation(payload: dict) -> str:
    inferred = next(
        a for a, e in payload["actions"].items() if e.get("provenance") == "name_inferred"
    )
    payload["actions"][inferred]["vendor_validated"] = True
    return f"claim a name-inferred route was vendor-validated ({inferred})"


def corrupt_a_reference(payload: dict) -> str:
    payload["actions"]["asana.tasks.create"]["api_reference"] = "tasks"
    return "store a reference with no HTTP method"


def main() -> int:
    mutations = [
        drop_an_action,
        strip_provenance,
        silence_a_no_endpoint_action,
        fake_vendor_validation,
        corrupt_a_reference,
    ]
    results: list[tuple[str, bool]] = []
    for mutate in mutations:
        payload = json.loads(ORIGINAL)
        label = mutate(payload)
        DATA.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_api_reference_map.py", "-q", "--no-header"],
            cwd=BACKEND,
            capture_output=True,
            text=True,
        )
        caught = proc.returncode != 0
        tail = [ln for ln in proc.stdout.splitlines() if ln.startswith("FAILED")]
        results.append((label, caught))
        print(f"{'CAUGHT ' if caught else 'MISSED '} {label}")
        for ln in tail:
            print(f"          {ln}")
        DATA.write_text(ORIGINAL, encoding="utf-8")

    print()
    missed = [label for label, caught in results if not caught]
    if missed:
        print("MUTATIONS NOT CAUGHT:")
        for label in missed:
            print(f"  {label}")
        return 1
    print(f"all {len(results)} mutations caught; data file restored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
