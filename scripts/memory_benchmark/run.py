"""Run only the canonical synthetic governance reference; vendor engines stay NOT_RUN."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
HERE = Path(__file__).resolve().parent

SOURCE_PATHS = (
    "backend/app/services/cognitive_turn_kernel.py", "backend/app/services/dialogue_memory_policy.py",
    "backend/app/services/memory_contamination_guard.py", "backend/app/services/workspace_memory_service.py",
    "backend/app/services/agent_memory_service.py", "backend/tests/support/governed_memory_benchmark.py",
    "scripts/memory_benchmark/cases.json", "scripts/memory_benchmark/contracts.py",
    "scripts/memory_benchmark/upstream_audit.json", "scripts/memory_benchmark/run.py",
)


async def run_reference():
    from tests.support.governed_memory_benchmark import execute_case

    cases = json.loads((HERE / "cases.json").read_text())
    rows = []
    for case in cases:
        started = time.perf_counter()
        try:
            row = await execute_case(case)
        except Exception:
            # No memory text, tenant/subject identity or exception body in reports.
            row = {"id": case["id"], "passed": False, "reason": "reference_error"}
        rows.append({**row, "latency_ms": round((time.perf_counter() - started) * 1000, 3)})
    return {
        "schema": 1, "benchmark_version": "governed-memory-v1", "data_scope": "fixed_synthetic_only",
        "status": "REFERENCE_GOVERNANCE_PASS" if all(r["passed"] for r in rows) else "FAIL",
        "scope": "real canonical kernel/policy/promotion code with fixture storage/retrievers; not vector ranking or provider performance",
        "latency_scope": "canonical_code_with_fixture_dependencies", "cost_usd": None,
        "production_certified": False, "case_count": len(rows), "passed": sum(r["passed"] for r in rows),
        "dataset_sha256": hashlib.sha256((HERE / "cases.json").read_bytes()).hexdigest(),
        "reference": rows,
        "candidate_results": [{"candidate": "mem0", "status": "NOT_RUN", "reason": "sdk_not_installed_or_invoked"},
                              {"candidate": "letta", "status": "NOT_RUN", "reason": "runtime_not_installed_or_invoked"}],
        "adoption_decision": "none", "external_memory_transfer": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT):
        raise SystemExit("Write reference reports outside the source checkout")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise SystemExit("A clean committed source is required for a reference report")
    from tests import offline_network as guard
    guard.pytest_configure(None)
    try:
        report = asyncio.run(run_reference())
        if guard._attempts:
            raise RuntimeError("Reference attempted external network")
        report.update({"source_sha": revision, "source_dirty": False, "external_attempts": 0,
                       "source_hashes": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCE_PATHS}})
    finally:
        guard.pytest_unconfigure(None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("source_sha", "status", "case_count", "passed", "candidate_results", "production_certified")}))
    if report["status"] != "REFERENCE_GOVERNANCE_PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
