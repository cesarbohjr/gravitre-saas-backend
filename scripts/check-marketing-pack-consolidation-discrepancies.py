#!/usr/bin/env python3
"""STA-298: Marketing Operations Pack post-consolidation discrepancy audit.

Usage:
  npm run marketing-pack:consolidation-discrepancies
  python scripts/check-marketing-pack-consolidation-discrepancies.py --json docs/delivery/marketing-pack-consolidation-discrepancies-latest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.marketplace.marketing_pack_consolidation_discrepancies import (  # noqa: E402
    audit_marketing_pack_consolidation_discrepancies,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="STA-298 marketing pack consolidation discrepancy audit")
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    report = audit_marketing_pack_consolidation_discrepancies()
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()

    summary = report["summary"]
    print(
        f"STA-298 consolidation discrepancies: {summary['confirmed']} confirmed, "
        f"{summary['partial']} partial, {summary['resolved']} resolved"
    )
    print(f"Recommendation: {report['recommendation']}")
    print(
        f"Connectors: {summary['oauthProviderCount']} OAuth providers, "
        f"{summary['catalogVendorCount']} catalog vendors"
    )
    if summary["riskItems"]:
        print(f"Risk items: {', '.join(summary['riskItems'])}")
    else:
        print("Risk items: none")
    print(f"Open discrepancies: {summary['openDiscrepancies']}")

    for section_key, label in (
        ("architecture", "Architecture"),
        ("executionAndNaming", "Execution + naming"),
        ("complianceAndDocs", "Compliance + documentation"),
    ):
        print(f"\n{label}:")
        for row in report[section_key]:
            status = row["liveState"].upper()
            match = "OK" if row["stateMatchesDoc"] else "DRIFT"
            print(f"  [{match}] {row['displayName']:48} {status:10} ({row['relatedIssue']})")

    if args.json_path:
        out_path = Path(args.json_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nReport: {out_path}")

    drift = [row for row in report["discrepancies"] if not row["stateMatchesDoc"]]
    if drift:
        print(f"\nWARNING: {len(drift)} discrepancy(ies) drift from documented state", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
