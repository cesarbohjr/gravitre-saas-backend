#!/usr/bin/env python3
"""STA-294: Marketing Operations Pack Mode A/B feedback product decision checklist.

Usage:
  npm run marketing-pack:mode-ab-decision
  python scripts/check-marketing-pack-mode-ab-decision.py --json docs/delivery/marketing-pack-mode-ab-decision-latest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.marketplace.marketing_pack_mode_ab_decision import audit_marketing_pack_mode_ab_decision  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="STA-294 Mode A/B product decision checklist")
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    report = audit_marketing_pack_mode_ab_decision()
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()

    summary = report["summary"]
    print(f"STA-294 Mode A/B decision: sign-off={report['signOffState']}")
    print(f"Pack default: {report.get('packDefaultFeedbackMode', 'mode_a')}")
    print(f"Product sign-off complete: {summary.get('productSignOffComplete')}")
    print(f"Engineering blocked (Mode B infra): {summary.get('engineeringBlocked')}")
    print(f"Engineering default: {report['engineeringRecommendedDefault']}")
    print(f"Assign to: {report['assignTo']}")
    print(
        f"Decisions: {summary['pending']} pending, {summary['blocked']} blocked, "
        f"{summary['resolved']} resolved"
    )
    print(f"Can ship Mode A default: {'yes' if summary['canShipModeADefault'] else 'no'}")
    print(f"Can ship Mode B: {'yes' if summary['canShipModeB'] else 'no'}")

    for row in report["decisions"]:
        status = row["status"].upper()
        print(f"  [{status:7}] {row['displayName']}")

    if args.json_path:
        out_path = Path(args.json_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nReport: {out_path}")

    if report["signOffState"] != "awaiting":
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
