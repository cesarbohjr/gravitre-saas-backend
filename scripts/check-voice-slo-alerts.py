#!/usr/bin/env python3
"""Standing two-metric voice SLO alerts (Metric A and Metric B separately).

Never treats a blended e2e number as the SLO. Writes
platform.voice_slo.alert when a threshold is breached and samples exist.
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

OUT = ROOT / "docs" / "delivery" / "voice-slo-alerts-latest.json"
WINDOW_HOURS = int(os.environ.get("VOICE_SLO_ALERT_HOURS", "24"))
MIN_SAMPLES = int(os.environ.get("VOICE_SLO_ALERT_MIN_SAMPLES", "3"))


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


def _pctl(vals: list[int], p: float) -> int | None:
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    idx = int(round((len(s) - 1) * p))
    return s[max(0, min(len(s) - 1, idx))]


def main() -> int:
    env = load_env()
    from supabase import create_client

    from app.services.voice_slo import (
        AUDIT_METRIC_A,
        AUDIT_METRIC_B,
        METRIC_A_P50_MS,
        METRIC_A_P95_MS,
        METRIC_B_P50_MS,
        METRIC_B_P95_MS,
    )
    from qa_signal_audit import write_platform_signal

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)).isoformat()

    def _ms(action: str) -> list[int]:
        rows = (
            sb.table("audit_events")
            .select("metadata,created_at")
            .eq("action", action)
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
            .data
            or []
        )
        out: list[int] = []
        for row in rows:
            val = _meta(row).get("ms")
            if isinstance(val, (int, float)):
                out.append(int(val))
        return out

    a_ms = _ms(AUDIT_METRIC_A)
    b_ms = _ms(AUDIT_METRIC_B)
    a_p50 = _pctl(a_ms, 0.5)
    a_p95 = _pctl(a_ms, 0.95)
    b_p50 = _pctl(b_ms, 0.5)
    b_p95 = _pctl(b_ms, 0.95)
    alerts: list[str] = []
    if len(a_ms) >= MIN_SAMPLES and a_p50 is not None and a_p50 > METRIC_A_P50_MS:
        alerts.append(f"voice_slo_metric_a_p50>{METRIC_A_P50_MS}ms")
    if len(a_ms) >= MIN_SAMPLES and a_p95 is not None and a_p95 > METRIC_A_P95_MS:
        alerts.append(f"voice_slo_metric_a_p95>{METRIC_A_P95_MS}ms")
    if len(b_ms) >= MIN_SAMPLES and b_p50 is not None and b_p50 > METRIC_B_P50_MS:
        alerts.append(f"voice_slo_metric_b_p50>{METRIC_B_P50_MS}ms")
    if len(b_ms) >= MIN_SAMPLES and b_p95 is not None and b_p95 > METRIC_B_P95_MS:
        alerts.append(f"voice_slo_metric_b_p95>{METRIC_B_P95_MS}ms")

    report = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": WINDOW_HOURS,
        "min_samples": MIN_SAMPLES,
        "blended_voice_latency": None,
        "metric_a": {
            "sample_count": len(a_ms),
            "p50_ms": a_p50,
            "p95_ms": a_p95,
            "hard_target_p50_ms": METRIC_A_P50_MS,
            "hard_target_p95_ms": METRIC_A_P95_MS,
        },
        "metric_b": {
            "sample_count": len(b_ms),
            "p50_ms": b_p50,
            "p95_ms": b_p95,
            "target_p50_ms": METRIC_B_P50_MS,
            "target_p95_ms": METRIC_B_P95_MS,
        },
        "alerts": alerts,
        "verdict": "ALERT" if alerts else "OK",
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if alerts:
        write_platform_signal(
            sb,
            action="platform.voice_slo.alert",
            verdict=f"ALERT — {'; '.join(alerts)}",
            metadata=report,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
