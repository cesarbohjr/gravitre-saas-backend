#!/usr/bin/env python3
"""STA-297: Marketing Operations Pack usage analytics audit (Phase 7.3).

Usage:
  npm run marketing-pack:usage-analytics-gaps
  python scripts/check-marketing-pack-usage-analytics-gaps.py --json docs/delivery/marketing-pack-usage-analytics-gaps-latest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.marketplace.marketing_pack_usage_analytics_gaps import (  # noqa: E402
    audit_marketing_pack_usage_analytics,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="STA-297 marketing pack usage analytics audit")
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    report = audit_marketing_pack_usage_analytics()
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()

    summary = report["summary"]
    print(
        f"STA-297 usage analytics: {summary['partial']} partial, "
        f"{summary['missing']} missing, {summary['exists']} exists"
    )
    print(f"Recommendation: {report['recommendation']}")
    if summary["measurementBlockers"]:
        print(f"Measurement blockers: {', '.join(summary['measurementBlockers'])}")
    else:
        print("Measurement blockers: none")
    if summary["packBlockers"]:
        print(f"Pack blockers: {', '.join(summary['packBlockers'])}")
    else:
        print(f"Pack blockers: none (v1 ready: {'yes' if summary['v1Ready'] else 'no'})")

    for section_key, label in (
        ("partialBatchOutcomes", "Partial batch outcomes"),
        ("hoursSavedMeasurement", "Hours saved measurement"),
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
