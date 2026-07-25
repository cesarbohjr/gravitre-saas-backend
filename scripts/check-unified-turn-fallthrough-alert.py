#!/usr/bin/env python3
"""Fallthrough threshold alert — writes platform.unified_turn_fallthrough.alert when breached."""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "docs" / "delivery" / "unified-turn-fallthrough-alert-latest.json"
ALERT_PCT = float(os.environ.get("UNIFIED_TURN_FALLTHROUGH_ALERT_PCT", "10"))
DEFER_SPIKE = int(os.environ.get("UNIFIED_TURN_FALLTHROUGH_DEFER_SPIKE", "15"))
WINDOW_HOURS = int(os.environ.get("UNIFIED_TURN_FALLTHROUGH_ALERT_HOURS", "24"))


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if p.is_file():
            merged.update({k: v for k, v in dotenv_values(p).items() if v})
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


def main() -> int:
    env = load_env()
    from supabase import create_client

    from qa_signal_audit import write_platform_signal

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)).isoformat()

    completed: list[dict] = []
    fallthrough: list[dict] = []
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
            if row.get("action") == "unified_turn.live.completed":
                completed.append(row)
            else:
                fallthrough.append(row)
        if len(batch) < 500:
            break
        offset += 500

    total = len(completed) + len(fallthrough)
    pct = round(100.0 * len(fallthrough) / total, 2) if total else 0.0
    defer_counts = Counter()
    for row in fallthrough:
        defer_counts[str(_meta(row).get("fallthrough_reason") or "unknown")] += 1

    alerts: list[str] = []
    if pct > ALERT_PCT:
        alerts.append(f"fallthrough_pct>{ALERT_PCT}%")
    defer_proposal = defer_counts.get("defer_connector_tool_proposal", 0)
    if defer_proposal >= DEFER_SPIKE:
        alerts.append(f"defer_connector_tool_proposal_spike>={DEFER_SPIKE}")

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": WINDOW_HOURS,
        "fallthrough_pct": pct,
        "live_total": total,
        "by_reason": dict(defer_counts),
        "alerts": alerts,
        "verdict": "ALERT" if alerts else "OK",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if alerts:
        write_platform_signal(
            sb,
            action="platform.unified_turn_fallthrough.alert",
            verdict=f"ALERT — {'; '.join(alerts)}",
            metadata=report,
            resource_id="fallthrough-alert",
        )
    print(json.dumps(report, indent=2))
    return 1 if alerts else 0


if __name__ == "__main__":
    raise SystemExit(main())
