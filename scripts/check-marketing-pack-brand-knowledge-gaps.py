#!/usr/bin/env python3
"""STA-295: Marketing Operations Pack brand/positioning knowledge store audit (Phase 7.1).

Usage:
  npm run marketing-pack:brand-knowledge-gaps
  python scripts/check-marketing-pack-brand-knowledge-gaps.py --json docs/delivery/marketing-pack-brand-knowledge-gaps-latest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.marketplace.marketing_pack_brand_knowledge_gaps import audit_marketing_pack_brand_knowledge  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="STA-295 marketing pack brand knowledge audit")
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    report = audit_marketing_pack_brand_knowledge()
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()

    summary = report["summary"]
    print(
        f"STA-295 brand knowledge: {summary['partial']} partial, "
        f"{summary['missing']} missing, {summary['exists']} exists"
    )
    print(f"Recommendation: {report['recommendation']}")
    print(f"v1 structured brand store required: {report['v1StructuredBrandStoreRequired']}")
    if summary["packBlockers"]:
        print(f"Pack blockers: {', '.join(summary['packBlockers'])}")
    else:
        print("Pack blockers: none")
    print(f"v1 ready (RAG-based): {'yes' if summary['v1Ready'] else 'no'}")

    for row in report["capabilities"]:
        status = row["liveState"].upper()
        match = "OK" if row["stateMatchesDoc"] else "DRIFT"
        print(f"  [{match}] {row['displayName']:46} {status:8}")

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
