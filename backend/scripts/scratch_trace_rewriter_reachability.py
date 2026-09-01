"""Why did the query-rewriter caller never run on the live probe turns?

The live proof recorded zero `retrieval.query.rewritten` events, which means
`agent_intelligence.py:2610` was not reached. Before concluding anything about
the fix, find out which path those turns actually took, and how often real
traffic reaches the rewriter at all.
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
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "docs" / "delivery" / "query-rewriter-reachability.json"


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

    since_recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    since_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    print("=== recent actions (last 2h), to see which path the probe turns took ===")
    rows = (
        sb.table("audit_events")
        .select("created_at,action,metadata")
        .gte("created_at", since_recent)
        .order("created_at", desc=True)
        .limit(400)
        .execute()
        .data
        or []
    )
    counts = Counter(r["action"] for r in rows)
    for action, n in counts.most_common(30):
        print(f"  {n:5d}  {action}")

    print("\n=== turn-path markers over 30 days ===")
    markers = [
        "retrieval.query.rewritten",
        "unified_turn.live.completed",
        "unified_turn.live.fallthrough",
        "answer.grounding.validated",
    ]
    summary = {}
    for action in markers:
        res = (
            sb.table("audit_events")
            .select("created_at,metadata", count="exact")
            .eq("action", action)
            .gte("created_at", since_30d)
            .limit(1)
            .execute()
        )
        total = res.count or 0
        summary[action] = total
        print(f"  {total:7d}  {action}")

    rewritten = (
        sb.table("audit_events")
        .select("created_at,metadata")
        .eq("action", "retrieval.query.rewritten")
        .gte("created_at", since_30d)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )
    if rewritten:
        print(f"\n=== most recent {len(rewritten)} rewrite events ===")
        for e in rewritten[:20]:
            md = e.get("metadata") or {}
            print(
                f"  {e['created_at']}  modelRan={md.get('modelRan')} "
                f"changed={md.get('changed')} mode={md.get('modeKey')}"
            )
    else:
        print("\nno retrieval.query.rewritten events at all in 30 days")
        print("(expected — the event only exists since this deploy)")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "recent_action_counts": dict(counts.most_common(40)),
                "marker_totals_30d": summary,
                "recent_rewrite_events": rewritten[:50],
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
