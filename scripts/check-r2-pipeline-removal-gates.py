#!/usr/bin/env python3
"""Automatic R2 old-pipeline removal gate tracker (fallthrough ≤1% + batteries green 7d).

Reads audit_events + latest battery artifacts. Writes platform.r2_removal_gates.sample
and exits 1 when gates are met (signal for automation) or alerts fire.
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

OUT = ROOT / "docs" / "delivery" / "r2-pipeline-removal-gates-latest.json"
BATTERY_ARTIFACTS = [
    ROOT / "docs" / "delivery" / "pending-reply-classifier-battery-live.json",
    ROOT / "docs" / "delivery" / "conversational-path-battery-live.json",
    ROOT / "docs" / "delivery" / "unified-turn-phase2-battery-live.json",
]
SOAK_DAYS = int(os.environ.get("R2_REMOVAL_SOAK_DAYS", "7"))
FALLTHROUGH_TARGET = float(os.environ.get("R2_REMOVAL_FALLTHROUGH_PCT", "1.0"))


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if p.is_file():
            merged.update({k: v for k, v in dotenv_values(p).items() if v})
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _read_battery(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def main() -> int:
    env = load_env()
    from supabase import create_client

    from qa_signal_audit import write_platform_signal

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(days=SOAK_DAYS)).isoformat()

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

    batteries: list[dict[str, Any]] = []
    batteries_green = True
    for path in BATTERY_ARTIFACTS:
        data = _read_battery(path)
        ok = False
        if data:
            verdict = str(data.get("verdict") or "")
            passed = data.get("passed")
            total_cases = data.get("total")
            ok = verdict == "PASS" or (
                isinstance(passed, int)
                and isinstance(total_cases, int)
                and passed == total_cases
                and total_cases > 0
            )
        batteries.append({"path": str(path.name), "ok": ok, "verdict": (data or {}).get("verdict")})
        batteries_green = batteries_green and ok

    deploy_rows = (
        sb.table("audit_events")
        .select("action,created_at,metadata")
        .eq("action", "platform.deploy_smoke.completed")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    deploy_green = bool(deploy_rows)

    ready = (
        pct <= FALLTHROUGH_TARGET
        and batteries_green
        and deploy_green
        and total >= 50
    )

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "soak_days": SOAK_DAYS,
        "fallthrough_pct_7d": pct,
        "fallthrough_target_pct": FALLTHROUGH_TARGET,
        "live_sample_n": total,
        "batteries": batteries,
        "batteries_green": batteries_green,
        "deploy_smoke_green_7d": deploy_green,
        "ready_for_r2_removal": ready,
        "verdict": "READY" if ready else "NOT_READY",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    write_platform_signal(
        sb,
        action="platform.r2_removal_gates.sample",
        verdict=report["verdict"],
        metadata=report,
        resource_id="r2-removal-gates",
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
