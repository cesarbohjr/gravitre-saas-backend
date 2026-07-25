#!/usr/bin/env python3
"""Battery-linked regression bisection — local pytest mapping for clean pass/fail cases.

When a standing battery fails, narrows to the culprit commit using git bisect and
case-specific pytest probes (no prod deploy per intermediate SHA required).

Usage:
  python scripts/battery_bisect.py --battery conversational --case meta_are_you_ai \\
    --good fbfc632f --bad HEAD

Writes docs/delivery/battery-bisect-<battery>-<case>.json

Deferred batteries (noisy/threshold): ttft, persona-drift (live-only), phase2-latency.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

# Case id → pytest node (must be deterministic pass/fail on commit).
CASE_PROBES: dict[str, dict[str, str]] = {
    "conversational": {
        "meta_are_you_ai": (
            "tests/services/test_unified_turn_reasoning.py::"
            "test_apply_unified_live_meta_capability_uses_expression_path[are you an AI?]"
        ),
        "meta_who_are_you": (
            "tests/services/test_unified_turn_reasoning.py::"
            "test_apply_unified_live_meta_capability_uses_expression_path[who are you?]"
        ),
    },
    "pending-reply": {
        "unrelated_hold": (
            "tests/services/test_unified_turn_reasoning.py::"
            "test_apply_unified_live_pending_unrelated_uses_hold_prompt"
        ),
    },
    "knowledge-boundary": {
        "qa_force_boundary": (
            "tests/services/test_unified_turn_reasoning.py::"
            "test_apply_unified_live_qa_force_knowledge_boundary"
        ),
    },
}

WIRED_BATTERIES = sorted(CASE_PROBES.keys())
DEFERRED = ["ttft", "persona-drift-live", "phase2-latency", "imperfect-input-live"]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_probe(probe: str) -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", probe, "-q", "--tb=no"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
    )
    return proc.returncode


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=str(ROOT), text=True).strip()


def bisect_run(good: str, bad: str, probe: str) -> dict[str, Any]:
    script = ROOT / "scripts" / "_battery_bisect_probe.sh"
    if sys.platform == "win32":
        # Windows: inline probe runner via python -c subprocess
        def test_commit() -> int:
            return run_probe(probe)

        # Manual binary search (git bisect run shell scripts are fragile on Windows)
        commits = git("rev-list", "--reverse", f"{good}..{bad}").splitlines()
        if not commits:
            return {"culprit": bad, "method": "direct_bad", "commits_tested": 0}
        lo, hi = 0, len(commits) - 1
        tested = 0
        while lo < hi:
            mid = (lo + hi) // 2
            sha = commits[mid]
            git("checkout", "-q", sha)
            tested += 1
            if test_commit() == 0:
                lo = mid + 1
            else:
                hi = mid
        culprit = commits[lo] if run_probe(probe) != 0 else commits[lo]
        git("checkout", "-q", bad)
        return {"culprit": culprit, "method": "binary_search", "commits_tested": tested + 1}

    script.write_text(
        f"""#!/bin/sh
cd "{BACKEND}" && {sys.executable} -m pytest "{probe}" -q --tb=no
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    git("bisect", "start", bad, good)
    try:
        subprocess.run(
            ["git", "bisect", "run", str(script)],
            cwd=str(ROOT),
            check=False,
        )
        culprit = git("rev-parse", "HEAD")
    finally:
        git("bisect", "reset")
    return {"culprit": culprit, "method": "git_bisect_run", "commits_tested": None}


def load_battery_history(battery: str, case: str) -> dict[str, Any]:
    paths = {
        "conversational": ROOT / "docs" / "delivery" / "conversational-path-battery-live.json",
        "pending-reply": ROOT / "docs" / "delivery" / "pending-reply-classifier-battery-live.json",
        "knowledge-boundary": ROOT / "docs" / "delivery" / "unified-turn-phase2-battery-live.json",
    }
    path = paths.get(battery)
    if not path or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    failed = [c for c in (data.get("cases") or data.get("results") or []) if not c.get("pass")]
    case_row = next(
        (c for c in (data.get("cases") or data.get("results") or []) if c.get("id") == case),
        None,
    )
    return {
        "artifact": str(path.name),
        "git_sha": data.get("git_sha"),
        "verdict": data.get("verdict"),
        "case_row": case_row,
        "failed_cases": [c.get("id") for c in failed],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Battery-linked regression bisection")
    parser.add_argument("--battery", required=True, choices=WIRED_BATTERIES)
    parser.add_argument("--case", required=True)
    parser.add_argument("--good", required=True, help="Last known-good commit SHA")
    parser.add_argument("--bad", default="HEAD", help="First known-bad commit SHA")
    parser.add_argument("--demo", action="store_true", help="Report-only demo mode")
    args = parser.parse_args()

    probes = CASE_PROBES.get(args.battery, {})
    probe = probes.get(args.case)
    if not probe:
        print(json.dumps({"error": f"case {args.case} not wired for {args.battery}"}, indent=2))
        return 2

    history = load_battery_history(args.battery, args.case)
    out_path = ROOT / "docs" / "delivery" / f"battery-bisect-{args.battery}-{args.case}.json"

    # Verify good passes and bad fails before bisect
    git("checkout", "-q", args.good)
    good_rc = run_probe(probe)
    git("checkout", "-q", args.bad)
    bad_rc = run_probe(probe)

    report: dict[str, Any] = {
        "started_at": utcnow(),
        "battery": args.battery,
        "case": args.case,
        "probe": probe,
        "good_sha": args.good,
        "bad_sha": args.bad,
        "good_probe_rc": good_rc,
        "bad_probe_rc": bad_rc,
        "battery_history": history,
        "wired_batteries": WIRED_BATTERIES,
        "deferred_batteries": DEFERRED,
    }

    if good_rc != 0:
        report["verdict"] = "NOT RUN — good_sha does not pass probe"
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2
    if bad_rc == 0:
        report["verdict"] = "NOT RUN — bad_sha still passes probe (no regression to bisect)"
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    if not args.demo:
        bisect_result = bisect_run(args.good, args.bad, probe)
        report["bisect"] = bisect_result
        culprit = bisect_result.get("culprit")
        if culprit:
            report["culprit_sha"] = culprit
            report["culprit_subject"] = git("log", "-1", "--format=%s", culprit)
            report["culprit_diff_stat"] = git("show", "--stat", "--format=", culprit)
    else:
        report["demo"] = True

    report["finished_at"] = utcnow()
    report["verdict"] = "PASS — culprit identified" if report.get("culprit_sha") else "PARTIAL"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "culprit": report.get("culprit_sha"), "out": str(out_path)}, indent=2))
    return 0 if report.get("culprit_sha") else 1


if __name__ == "__main__":
    raise SystemExit(main())
