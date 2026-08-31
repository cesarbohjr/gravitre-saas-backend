"""Before/after evidence that the grounding validator actually runs.

A swallowed TypeError returns in about a millisecond. A real model call does
not. So the validation stage's own recorded latency separates "the check ran"
from "the check was a no-op" without needing to trust any self-report, and it
measures the added cost at the same time.

Usage:
  python scripts/probe_validation_stage_latency.py before
  python scripts/probe_validation_stage_latency.py after
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT = ROOT / "docs" / "delivery" / "validation-stage-latency.json"


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env"):
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
    phase = (sys.argv[1] if len(sys.argv) > 1 else "before").strip().lower()
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("ai_pipeline_latency")
        .select("id,org_id,stage_name,duration_ms,tier,created_at")
        .eq("stage_name", "validation")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(500)
        .execute()
        .data
        or []
    )

    durations = sorted(int(r.get("duration_ms") or 0) for r in rows)
    n = len(durations)
    summary = {
        "phase": phase,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "window": "last 30 days",
        "samples": n,
        "min_ms": durations[0] if n else None,
        "median_ms": durations[n // 2] if n else None,
        "max_ms": durations[-1] if n else None,
        "under_5ms": sum(1 for d in durations if d < 5),
        "over_100ms": sum(1 for d in durations if d > 100),
        "newest_rows": rows[:5],
    }

    # A no-op stage is sub-millisecond; a real model call is not. This is the
    # discriminator, stated up front so the reading is not retrofitted.
    if n:
        share_noop = summary["under_5ms"] / n
        summary["reading"] = (
            f"{summary['under_5ms']}/{n} samples under 5ms "
            f"({share_noop:.0%}) — consistent with a swallowed error, not a model call"
            if share_noop > 0.8
            else f"{summary['over_100ms']}/{n} samples over 100ms — consistent with a real model call"
        )
    else:
        summary["reading"] = "no validation-stage rows in window"

    existing = {}
    if OUT.is_file():
        try:
            existing = json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    existing[phase] = summary
    OUT.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")

    print(json.dumps({k: v for k, v in summary.items() if k != "newest_rows"}, indent=2))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
