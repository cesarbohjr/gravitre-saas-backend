#!/usr/bin/env python3
"""STA-300/301: Department pack pricing framework + Marketing Operations Pack checkout audit.

Usage:
  npm run marketing-pack:pricing-gaps
  python scripts/check-marketing-pack-pricing-gaps.py --json docs/delivery/marketing-pack-pricing-gaps-latest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.marketplace.marketing_pack_pricing_gaps import audit_marketing_pack_pricing  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="STA-300/301 marketing pack pricing audit")
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    report = audit_marketing_pack_pricing()
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()

    summary = report["summary"]
    print(
        f"STA-300/301 pricing: {summary['partial']} partial, "
        f"{summary['missing']} missing, {summary['exists']} exists"
    )
    print(f"Recommendation: {report['recommendation']}")
    print(f"Framework ready: {'yes' if summary['frameworkReady'] else 'no'}")
    print(f"Marketing pack live ready: {'yes' if summary['marketingPackLiveReady'] else 'no'}")
    print(f"v1 ready: {'yes' if summary['v1Ready'] else 'no'}")

    for section_key, label in (
        ("framework", "Framework (STA-300)"),
        ("marketingPackLive", "Marketing pack live (STA-301)"),
        ("openGaps", "Open gaps"),
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
