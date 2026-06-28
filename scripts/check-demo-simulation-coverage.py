#!/usr/bin/env python3
"""STA-285: Demo-safe simulation coverage audit — zero coverage = demo-blocked."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.connectors.simulation_coverage import build_simulation_coverage_report  # noqa: E402


def main() -> int:
    report = build_simulation_coverage_report()
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()

    blocked = [
        v["vendor"]
        for v in report["vendors"]
        if not v.get("demoReady") and v.get("found")
    ]
    zero_cov = [
        v["vendor"]
        for v in report["vendors"]
        if v.get("zeroCoverageTools") and v.get("found")
    ]

    out_path = REPO_ROOT / "docs" / "delivery" / "demo-simulation-coverage-latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    summary = report["summary"]
    print(
        f"Simulation coverage: {summary['demoReadyVendors']}/{summary['vendorCount']} vendors demo-ready"
    )
    print(f"Zero-coverage vendors: {', '.join(zero_cov) or 'none'}")
    print(f"Demo-blocked vendors: {', '.join(blocked) or 'none'}")
    print(f"\nReport: {out_path}")

    # Exit non-zero when any non-excluded vendor has zero implementation coverage
    hard_fail = [v for v in zero_cov if v not in report["demoExcludedVendors"]]
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
