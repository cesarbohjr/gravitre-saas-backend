#!/usr/bin/env python3
"""STA-293: Marketing Operations Pack outcome feedback loop audit (Phase 6.2).

Usage:
  npm run marketing-pack:feedback-loop-gaps
  python scripts/check-marketing-pack-feedback-loop-gaps.py --json docs/delivery/marketing-pack-feedback-loop-gaps-latest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.marketplace.marketing_pack_feedback_loop_gaps import audit_marketing_pack_feedback_loop  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="STA-293 marketing pack feedback loop audit")
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    report = audit_marketing_pack_feedback_loop()
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()

    summary = report["summary"]
    mode_a = summary["modeA"]
    mode_b = summary["modeB"]
    print(
        f"STA-293 feedback loop: Mode A {mode_a['partial']} partial / {mode_a['missing']} missing / "
        f"{mode_a['exists']} exists; Mode B {mode_b['missing']} missing (net-new)"
    )
    print(f"Recommended default: {report['recommendedDefault']} (product sign-off: {report['productDecisionTicket']})")
    if summary["packBlockers"]:
        print(f"Pack blockers: {', '.join(summary['packBlockers'])}")
    else:
        print("Pack blockers: none (Mode A default viable)")

    for section_key, label in (("modeA", "Mode A"), ("modeB", "Mode B"), ("shared", "Shared")):
        print(f"\n{label}:")
        for row in report[section_key]:
            status = row["liveState"].upper()
            match = "OK" if row["stateMatchesDoc"] else "DRIFT"
            print(f"  [{match}] {row['displayName']:42} {status:8}")

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
