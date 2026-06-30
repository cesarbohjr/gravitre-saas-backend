#!/usr/bin/env python3
"""STA-299: Marketing Operations Pack reusability audit (Phase 7.4).

Usage:
  npm run marketing-pack:reusability-gaps
  python scripts/check-marketing-pack-reusability-gaps.py --json docs/delivery/marketing-pack-reusability-gaps-latest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.marketplace.marketing_pack_reusability_gaps import audit_marketing_pack_reusability  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="STA-299 marketing pack reusability audit")
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    report = audit_marketing_pack_reusability()
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()

    summary = report["summary"]
    print(
        f"STA-299 reusability: {summary['partial']} partial, "
        f"{summary['missing']} missing, {summary['exists']} exists"
    )
    print(f"Recommendation: {report['recommendation']}")
    print(
        f"General primitives ready: {'yes' if summary['generalPrimitivesReady'] else 'no'} "
        f"({summary['generalPrimitiveCount']} items)"
    )
    if summary["futurePackBlockers"]:
        print(f"Future pack blockers: {', '.join(summary['futurePackBlockers'])}")
    else:
        print(f"Future pack blockers: none (next pack ready: {'yes' if summary['nextPackReady'] else 'no'})")

    for section_key, label in (
        ("generalPrimitives", "General primitives"),
        ("marketingSpecific", "Marketing-specific"),
        ("openUncertainties", "Open uncertainties"),
    ):
        print(f"\n{label}:")
        for row in report[section_key]:
            status = row["liveState"].upper()
            match = "OK" if row["stateMatchesDoc"] else "DRIFT"
            print(f"  [{match}] {row['displayName']:48} {status:8}")

    if args.json_path:
        out_path = Path(args.json_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nReport: {out_path}")

    drift = [row for row in report["capabilities"] if not row["stateMatchesDoc"]]
    if drift:
        print(f"\nWARNING: {len(drift)} capability(ies) drift from documented audit state", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
