"""Master audit-to-remediation evidence compiler.

Read-only; no deployment, provider traffic, secrets or status mutation.
Fails on disappearing findings, ownership ambiguity, unproven PASS and
unapproved retirement. Live/routing/cost proof is NEVER synthesized from imports.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/delivery/master-qa-tranche27-findings-evidence-matrix.json"
REGISTER = ROOT / "docs/delivery/master-qa-remediation-register.v2.json"
PASS_STATUSES = {"PASS", "CERTIFIED"}
SHA = re.compile(r"^[0-9a-f]{40}$")
QA_LANES = {"QA00", "QA10", "QA20", "QA30", "QA40", "QA50", "QA90"}
OWNERS = {"PR610-voice (PR611 integration gate)", "PR611-cross-platform"}


class RemediationError(ValueError):
    pass


def evaluate(root: Path = ROOT, *, original: dict | None = None,
             register: dict | None = None) -> dict:
    if original is None:
        original = json.loads((root / SOURCE.relative_to(ROOT)).read_text())
    if register is None:
        register = json.loads((root / REGISTER.relative_to(ROOT)).read_text())
    rows = register.get("records")
    if not isinstance(rows, list):
        raise RemediationError("records must be a list")
    source_ids = [row["finding_id"] for row in original["entries"]]
    ids = [row.get("finding_id") for row in rows]
    errors: list[str] = []
    if len(set(ids)) != len(ids):
        errors.append("duplicate finding IDs")
    if set(ids) != set(source_ids):
        errors.append("finding coverage mismatch: missing="
                      + repr(sorted(set(source_ids) - set(ids)))
                      + " extra=" + repr(sorted(set(ids) - set(source_ids))))
    if register.get("finding_count") != len(rows):
        errors.append("declared finding count differs from actual register")
    if register.get("baseline_source_sha") != original.get("source_main_sha"):
        errors.append("audit source snapshot mismatch")

    for row in rows:
        fid = str(row.get("finding_id"))
        prefix = fid + ": "
        if row.get("severity") not in {"P0", "P1", "P2", "P3"}:
            errors.append(prefix + "severity absent or invalid")
        if row.get("qa_lane") not in QA_LANES:
            errors.append(prefix + "QA lane unmapped")
        if row.get("implementation_owner") not in OWNERS:
            errors.append(prefix + "unrecognized implementation owner")
        if not row.get("owner") or not row.get("affected_chain") or not row.get("remediation"):
            errors.append(prefix + "missing accountable owner/chain/repair")
        if len(row.get("closure_criteria") or []) < 4:
            errors.append(prefix + "insufficient acceptance criteria")
        if row.get("root_cause") == "CONFIRMED" and not row.get("source_to_runtime_trace"):
            errors.append(prefix + "confirmed root cause without runtime trace")
        path = (row.get("source_probe") or {}).get("path")
        if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
            errors.append(prefix + "invalid source probe path")
        elif not (root / path).is_file():
            # Missing real code is an audit defect, not a legitimate PASS.
            errors.append(prefix + "source probe missing: " + path)
        evidence = row.get("evidence") or {}
        claimed_pass = row.get("synthetic_status") in PASS_STATUSES or row.get("live_status") in PASS_STATUSES
        claimed_pass = claimed_pass or bool(row.get("fix_verified"))
        if claimed_pass:
            commit = row.get("implemented_commit")
            if not isinstance(commit, str) or not SHA.fullmatch(commit):
                errors.append(prefix + "PASS without exact implementing SHA")
            if not row.get("regression_candidate"):
                errors.append(prefix + "PASS without executable regression")
            if not row.get("negative_test_verified") or not row.get("downstream_effect_verified"):
                errors.append(prefix + "PASS without negative and downstream-effect proof")
            if not row.get("source_to_runtime_trace"):
                errors.append(prefix + "PASS without actual caller-to-runtime evidence")
            if not row.get("rollback_verified"):
                errors.append(prefix + "PASS without validated rollback")
            if not row.get("owner_approval"):
                errors.append(prefix + "PASS without owner approval")
            if not evidence.get("ci_run_url") or evidence.get("executed_sha") != commit:
                errors.append(prefix + "PASS without same-SHA CI artifact")
            if not evidence.get("deploy_sha") and row.get("live_status") in PASS_STATUSES:
                errors.append(prefix + "live PASS without deployment SHA")
            if row.get("domain") in {"connector-wiring", "governed-actions", "uncertain-write-recovery"} and not evidence.get("provider_readback"):
                errors.append(prefix + "provider PASS without source-of-record readback")
        if row.get("retirement_authorized") and (
            not row.get("fix_verified") or not row.get("owner_approval")
            or not row.get("rollback_verified") or not row.get("source_to_runtime_trace")
        ):
            errors.append(prefix + "unsafe retirement authorization")
        if (fid in {"ECO-004","ECO-009","P27-07","DEC-010","DEC-014"}
                and row.get("implementation_owner") != "PR610-voice (PR611 integration gate)"):
            errors.append(prefix + "Voice 3.0 implementation belongs to PR610")
    if register.get("global_release_authorized") and any(
        row.get("release_blocking") and not row.get("fix_verified") for row in rows
    ):
        errors.append("global release authorized with unresolved P0 findings")
    if errors:
        raise RemediationError("\n".join(errors))
    return {
        "schema_version": 1,
        "source_only": True,
        "findings": len(rows),
        "severity_counts": dict(sorted(Counter(r["severity"] for r in rows).items())),
        "qa_lanes": dict(sorted(Counter(r["qa_lane"] for r in rows).items())),
        "closure_count": sum(bool(r.get("fix_verified")) for r in rows),
        "blocked_p0": sum(r["severity"] == "P0" and not r.get("fix_verified") for r in rows),
        "missing_regression_candidates": [
            r["finding_id"] for r in rows if not r.get("regression_candidate")
        ],
        "release_authorized": bool(register.get("global_release_authorized")),
        "note": "Source-level ledger validation only; no production deployment, telemetry or provider readback inferred.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
