#!/usr/bin/env python3
"""STA-292: Marketing Operations Pack connector gap audit (Phase 6.1).

Usage:
  npm run marketing-pack:connector-gaps
  python scripts/check-marketing-pack-connector-gaps.py --json docs/delivery/marketing-pack-connector-gaps-latest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.marketplace.marketing_pack_connector_gaps import audit_marketing_pack_connectors  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="STA-292 marketing pack connector gap audit")
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    report = audit_marketing_pack_connectors()
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()

    summary = report["summary"]
    print(
        f"STA-292 connector gaps: {summary['partial']} partial, "
        f"{summary['missing']} missing, {summary['exists']} exists"
    )
    if summary["packBlockers"]:
        print(f"Pack blockers: {', '.join(summary['packBlockers'])}")
    else:
        print("Pack blockers: none")

    for row in report["connectors"]:
        status = row["liveState"].upper()
        tools = ""
        if row["catalogTools"]:
            tools = f" tools={row['implementedTools']}/{row['catalogTools']}"
        match = "OK" if row["stateMatchesDoc"] else "DRIFT"
        print(f"  [{match}] {row['displayName']:28} {status:8}{tools}")

    if args.json_path:
        out_path = Path(args.json_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nReport: {out_path}")

    drift = [row for row in report["connectors"] if not row["stateMatchesDoc"]]
    if drift:
        print(f"\nWARNING: {len(drift)} connector(s) drift from documented audit state", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
