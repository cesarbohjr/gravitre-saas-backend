"""Audit the pinned source checkout without executing or importing upstream code.

Usage: python scripts/audit-agency-agents.py /path/to/agency-agents [--check]
Only provenance is written; external role instructions never enter runtime prompts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

INVENTORY = Path(__file__).resolve().parents[1] / "backend/app/marketplace/agency_agents_inventory.json"


def audit(root: Path, data: dict) -> dict:
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True,
    ).strip()
    if revision != data["source_commit"]:
        raise ValueError("source_revision_mismatch")
    # Reject dirty tracked sources, including staged changes; untracked files
    # are also caught by the filesystem census below if they are profiles.
    subprocess.run(["git", "-C", str(root), "diff", "--exit-code", "HEAD"], check=True, capture_output=True)
    license_bytes = (root / "LICENSE").read_bytes()
    if not license_bytes.startswith(b"MIT License"):
        raise ValueError("unexpected_license")
    divisions = json.loads((root / "divisions.json").read_text())["divisions"]
    if set(divisions) != set(data["divisions"]):
        raise ValueError("division_census_mismatch")
    profiles = {
        str(p.relative_to(root)): p
        for division in divisions for p in (root / division).rglob("*.md")
        if p.read_text(encoding="utf-8").startswith("---\n")
    }
    if set(profiles) != {a["source_path"] for a in data["agents"]}:
        raise ValueError("profile_census_mismatch")
    for agent in data["agents"]:
        path = profiles[agent["source_path"]]
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("unsafe_source_path")
        raw = path.read_bytes()
        frontmatter = raw.decode("utf-8").split("---", 2)[1]
        if not any(line.startswith("name:") and line[5:].strip() for line in frontmatter.splitlines()):
            raise ValueError("missing_profile_name")
        agent["source_sha256"] = hashlib.sha256(raw).hexdigest()
        agent["source_license"] = "MIT"
    data["source_audit"] = {
        "revision": revision,
        "license": "MIT",
        "license_sha256": hashlib.sha256(license_bytes).hexdigest(),
        "profile_count": len(profiles),
        "coverage": "all_frontmatter_profiles_in_declared_divisions",
        "excluded_directories": ["examples", "integrations", "scripts", "strategy"],
        "runtime_text_imported": False,
    }
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    original = INVENTORY.read_text(encoding="utf-8")
    result = json.dumps(audit(args.checkout, json.loads(original)), indent=2) + "\n"
    if args.check:
        if result != original:
            raise SystemExit("Inventory provenance differs; run audit without --check")
    else:
        INVENTORY.write_text(result, encoding="utf-8")
    print("Verified pinned source profiles and MIT license; no upstream code executed")
