#!/usr/bin/env python3
"""TTFT threshold alert — writes platform.unified_turn_ttft.alert when breached.

Mirrors check-unified-turn-fallthrough-alert.py. Thresholds (ms):
  UNIFIED_TURN_TTFT_ALERT_P50_MS (default 1500)
  UNIFIED_TURN_TTFT_ALERT_P99_MS (default 5000)
  UNIFIED_TURN_TTFT_ALERT_MAX_MS (default 10000)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "docs" / "delivery" / "unified-turn-ttft-alert-latest.json"
ALERT_P50 = int(os.environ.get("UNIFIED_TURN_TTFT_ALERT_P50_MS", "1500"))
ALERT_P99 = int(os.environ.get("UNIFIED_TURN_TTFT_ALERT_P99_MS", "5000"))
ALERT_MAX = int(os.environ.get("UNIFIED_TURN_TTFT_ALERT_MAX_MS", "10000"))
WINDOW_HOURS = int(os.environ.get("UNIFIED_TURN_TTFT_ALERT_HOURS", "24"))


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if p.is_file():
            for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
                try:
                    merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                    break
                except UnicodeDecodeError:
                    continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def _wall_ms(meta: dict[str, Any]) -> int | None:
    bd = meta.get("latency_breakdown") or {}
    if not isinstance(bd, dict):
        bd = {}
    raw = meta.get("first_token_proxy_ms")
    if raw is None:
        raw = bd.get("wall_to_first_token_ms")
    if isinstance(raw, (int, float)):
        return int(raw)
    return None


def _pct(sorted_vals: list[int], p: float) -> int | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = int(round((len(sorted_vals) - 1) * p))
    return sorted_vals[max(0, min(len(sorted_vals) - 1, idx))]


def main() -> int:
    env = load_env()
    from supabase import create_client

    from qa_signal_audit import write_platform_signal

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)).isoformat()

    walls: list[int] = []
    offset = 0
    while True:
        batch = (
            sb.table("audit_events")
            .select("action,created_at,metadata")
            .in_("action", ["unified_turn.live.completed", "unified_turn.live.fallthrough"])
            .gte("created_at", since)
            .order("created_at", desc=True)
            .range(offset, offset + 499)
            .execute()
            .data
            or []
        )
        if not batch:
            break
        for row in batch:
            wall = _wall_ms(_meta(row))
            if wall is not None:
                walls.append(wall)
        if len(batch) < 500:
            break
        offset += 500

    ordered = sorted(walls)
    p50 = _pct(ordered, 0.50)
    p99 = _pct(ordered, 0.99)
    mx = ordered[-1] if ordered else None

    alerts: list[str] = []
    if p50 is not None and p50 > ALERT_P50:
        alerts.append(f"ttft_p50>{ALERT_P50}ms")
    if p99 is not None and p99 > ALERT_P99:
        alerts.append(f"ttft_p99>{ALERT_P99}ms")
    if mx is not None and mx > ALERT_MAX:
        alerts.append(f"ttft_max>{ALERT_MAX}ms")

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": WINDOW_HOURS,
        "sample_count": len(ordered),
        "wall_p50_ms": p50,
        "wall_p99_ms": p99,
        "wall_max_ms": mx,
        "thresholds_ms": {"p50": ALERT_P50, "p99": ALERT_P99, "max": ALERT_MAX},
        "alerts": alerts,
        "verdict": "ALERT" if alerts else "OK",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if alerts:
        write_platform_signal(
            sb,
            action="platform.unified_turn_ttft.alert",
            verdict=f"ALERT — {'; '.join(alerts)}",
            metadata=report,
            resource_id="ttft-alert",
        )
    print(json.dumps(report, indent=2))
    return 1 if alerts else 0


if __name__ == "__main__":
    raise SystemExit(main())
