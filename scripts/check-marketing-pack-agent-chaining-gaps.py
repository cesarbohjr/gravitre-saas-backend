#!/usr/bin/env python3
"""STA-291: Marketing Operations Pack agent chaining audit (Phase 5.1).

Usage:
  npm run marketing-pack:agent-chaining-gaps
  python scripts/check-marketing-pack-agent-chaining-gaps.py --json docs/delivery/marketing-pack-agent-chaining-gaps-latest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.marketplace.marketing_pack_agent_chaining_gaps import audit_marketing_pack_agent_chaining  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="STA-291 marketing pack agent chaining audit")
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    report = audit_marketing_pack_agent_chaining()
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()

    summary = report["summary"]
    print(
        f"STA-291 agent chaining: {summary['partial']} partial, "
        f"{summary['missing']} missing, {summary['exists']} exists"
    )
    print(f"Recommendation: {report['recommendation']}")
    if summary["packBlockers"]:
        print(f"Pack blockers: {', '.join(summary['packBlockers'])}")
    else:
        print(f"Pack blockers: none (v1 ready: {'yes' if summary['v1Ready'] else 'no'})")

    for section_key, label in (("catalog", "Catalog"), ("runtime", "Runtime"), ("versioning", "Versioning")):
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
