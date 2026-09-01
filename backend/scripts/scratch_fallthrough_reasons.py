"""What actually causes unified-turn-live fallthrough in real production traffic?

The classical path — which is where the query rewriter and the grounding
validator live — only runs when the unified turn declines to serve. To live-prove
the rewriter, a turn shape that genuinely falls through is needed. Rather than
guess at one, read the reasons real traffic recorded.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "delivery" / "unified-turn-fallthrough-reasons.json"


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    return merged


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    rows = (
        sb.table("audit_events")
        .select("created_at,metadata")
        .eq("action", "unified_turn.live.fallthrough")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(1000)
        .execute()
        .data
        or []
    )
    print(f"fallthrough events sampled: {len(rows)}\n")

    reasons = Counter()
    keysets = Counter()
    for r in rows:
        md = r.get("metadata") or {}
        reasons[str(md.get("fallthroughReason") or md.get("fallthrough_reason") or "(none)")] += 1
        keysets[tuple(sorted(md.keys()))] += 1

    print("=== fallthrough reasons ===")
    for reason, n in reasons.most_common(25):
        print(f"  {n:6d}  {reason}")

    print("\n=== metadata shapes seen (to find the right field name) ===")
    for keys, n in keysets.most_common(3):
        print(f"  {n:6d}  {list(keys)}")

    if rows:
        print("\n=== one full example ===")
        print(json.dumps(rows[0], indent=2, default=str)[:1500])

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "sampled": len(rows),
                "reasons": dict(reasons.most_common()),
                "example": rows[0] if rows else None,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
