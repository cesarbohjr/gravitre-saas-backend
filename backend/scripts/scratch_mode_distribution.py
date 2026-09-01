"""What effective mode does real traffic actually run in?

The rewriter (agent_intelligence.py:2610) is gated behind `mode_key != "fast"`.
The region around it is proven reached daily, production is confirmed running the
instrumented commit, and still zero rewriter events — which points at the gate.

If unified-turn telemetry records the mode, the fast share can be measured from
real traffic now, without waiting on a new deploy.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import fetch_all, load_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "delivery" / "effective-mode-distribution.json"

MODE_HINT_KEYS = ("mode", "modeKey", "effectiveMode", "effective_mode", "tier", "routingTier")


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    findings: dict[str, dict] = {}
    for action in (
        "unified_turn.live.completed",
        "unified_turn.live.fallthrough",
        "agent.react.iteration",
        "inference.tool_completion",
    ):
        rows = fetch_all(sb, action, since, "created_at,resource_type,metadata")
        keyset = Counter()
        per_key: dict[str, Counter] = {k: Counter() for k in MODE_HINT_KEYS}
        for r in rows:
            md = r.get("metadata") or {}
            if not isinstance(md, dict):
                continue
            keyset[tuple(sorted(md.keys()))] += 1
            for k in MODE_HINT_KEYS:
                if k in md:
                    per_key[k][str(md.get(k))] += 1

        print(f"\n=== {action}  (n={len(rows)}) ===")
        if keyset:
            keys, n = keyset.most_common(1)[0]
            print(f"  most common metadata keys ({n}): {list(keys)}")
        found_any = False
        for k in MODE_HINT_KEYS:
            if per_key[k]:
                found_any = True
                print(f"  {k}: {dict(per_key[k].most_common(10))}")
        if not found_any:
            print("  (no mode-bearing field recorded)")
        findings[action] = {
            "count": len(rows),
            "mode_fields": {k: dict(v.most_common()) for k, v in per_key.items() if v},
            "sample_keys": [list(k) for k, _ in keyset.most_common(3)],
        }

    OUT.write_text(
        json.dumps(
            {"captured_at": datetime.now(timezone.utc).isoformat(), "findings": findings},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
