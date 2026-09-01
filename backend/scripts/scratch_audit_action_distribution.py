"""Which audit actions carry real volume in the last 30 days?

conversation_messages turned out not to persist the terminal model label, so the
region-reach question has to be answered from audit events instead. Several
emitters sit unambiguously inside the classical region (assistant.routing.escalated
at agent_intelligence.py:3250, and every ReAct tool.invoke.* event, since the
ReAct engine is invoked at :3221 — both well past the region entry at :2608).

If those show real volume, the region is alive and the two zero-event instruments
were measuring narrower branches than assumed.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import load_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "delivery" / "audit-action-distribution.json"


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    rows: list[dict] = []
    page = 0
    while True:
        chunk = (
            sb.table("audit_events")
            .select("action,created_at")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .range(page * 1000, page * 1000 + 999)
            .execute()
            .data
            or []
        )
        rows.extend(chunk)
        if len(chunk) < 1000:
            break
        page += 1
        if page > 40:
            print("(stopped at 40k rows)")
            break

    counts = Counter(str(r.get("action") or "") for r in rows)
    print(f"audit events in 30d: {len(rows)}\n")
    print("=== action distribution ===")
    for action, n in counts.most_common(80):
        print(f"  {n:7d}  {action}")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "window_days": 30,
                "total_events": len(rows),
                "actions": dict(counts.most_common()),
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
