#!/usr/bin/env python3
"""Standing two-metric voice SLO alerts (Metric A and Metric B separately).

Never treats a blended e2e number as the SLO. Writes
platform.voice_slo.alert when a threshold is breached and samples exist.
Exits 1 on a breach and 2 when either metric has too few samples to judge.

Samples are the ``voice.slo.metric_a`` / ``voice.slo.metric_b`` audit rows the
production voice turn path writes (voice_session_service -> record_voice_slo_metric).

Set ``VOICE_SLO_ALERT_ORG_ID`` to judge one org's samples (CI sets it to the
isolated smoke org right after the live probe drives HTTP Talk there). The
all-org window is still read and reported, and a breach there still alerts, so
scoping never hides a customer regression. PASS needs >= MIN_SAMPLES in both
metrics of the judged scope with every target met; anything less is NO_DATA.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "docs" / "delivery" / "voice-slo-alerts-latest.json"
WINDOW_HOURS = int(os.environ.get("VOICE_SLO_ALERT_HOURS", "24"))
MIN_SAMPLES = int(os.environ.get("VOICE_SLO_ALERT_MIN_SAMPLES", "3"))

# Must match app.services.voice_slo (main() asserts it, and so do the tests).
# Kept here so the pure evaluation below is testable without Supabase.
TARGETS = {
    "metric_a": {"p50": 500, "p95": 800},
    "metric_b": {"p50": 5000, "p95": 8000},
}


def load_env() -> dict[str, str]:
    from dotenv import dotenv_values

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
    idx = round((len(s) - 1) * p)
    return s[max(0, min(len(s) - 1, idx))]


def samples_ms(rows: list[dict[str, Any]]) -> list[int]:
    """Numeric ``ms`` values from audit rows; rows without a real number are dropped."""
    out: list[int] = []
    for row in rows:
        val = _meta(row).get("ms")
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        out.append(int(val))
    return out


def summarize(a_ms: list[int], b_ms: list[int], *, label: str, min_samples: int) -> dict[str, Any]:
    """One scope: counts, percentiles, breaches, and which metrics are too short to judge."""
    out: dict[str, Any] = {"scope": label}
    alerts: list[str] = []
    short: list[str] = []
    suffix = "" if label == "all_orgs" else f"[{label}]"
    for name, vals in (("metric_a", a_ms), ("metric_b", b_ms)):
        p50, p95 = _pctl(vals, 0.5), _pctl(vals, 0.95)
        tgt = TARGETS[name]
        prefix = "hard_target" if name == "metric_a" else "target"
        out[name] = {
            "sample_count": len(vals),
            "p50_ms": p50,
            "p95_ms": p95,
            f"{prefix}_p50_ms": tgt["p50"],
            f"{prefix}_p95_ms": tgt["p95"],
        }
        if len(vals) < min_samples:
            short.append(name)
            continue
        if p50 is not None and p50 > tgt["p50"]:
            alerts.append(f"voice_slo_{name}_p50>{tgt['p50']}ms{suffix}")
        if p95 is not None and p95 > tgt["p95"]:
            alerts.append(f"voice_slo_{name}_p95>{tgt['p95']}ms{suffix}")
    out["alerts"] = alerts
    out["insufficient_samples"] = short
    return out


def evaluate(
    all_orgs: dict[str, Any],
    scoped: dict[str, Any] | None = None,
) -> tuple[str, list[str], list[str]]:
    """Return (verdict, alerts, short_metrics) for the judged scope.

    The judged scope is ``scoped`` when given, else ``all_orgs``. A breach in
    either scope is ALERT. Otherwise PASS needs the judged scope to have enough
    samples in both metrics; too few is NO_DATA, never PASS.
    """
    judged = scoped if scoped is not None else all_orgs
    alerts = list(all_orgs["alerts"])
    if scoped is not None:
        alerts.extend(a for a in scoped["alerts"] if a not in alerts)
    short = list(judged["insufficient_samples"])
    if alerts:
        return "ALERT", alerts, short
    if short:
        return "NO_DATA", [], short
    return "PASS", [], []


def build_report(
    all_orgs: dict[str, Any],
    scoped: dict[str, Any] | None,
    *,
    window_hours: int,
    min_samples: int,
) -> dict[str, Any]:
    verdict, alerts, short = evaluate(all_orgs, scoped)
    judged = scoped if scoped is not None else all_orgs
    report: dict[str, Any] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": window_hours,
        "min_samples": min_samples,
        "blended_voice_latency": None,
        "judged_scope": judged["scope"],
        "metric_a": judged["metric_a"],
        "metric_b": judged["metric_b"],
        "all_orgs": {k: all_orgs[k] for k in ("metric_a", "metric_b", "alerts")},
        "alerts": alerts,
        "verdict": verdict,
    }
    if scoped is not None:
        report["scope_note"] = (
            "Judged samples are the scoped org's own voice.slo.metric_a/metric_b "
            "audit rows. For the isolated smoke org these are real production HTTP "
            "Talk turns driven by the live probe, not customer traffic."
        )
    if short:
        report["insufficient_samples"] = short
    return report


def main() -> int:
    env = load_env()
    from app.services.voice_slo import (
        AUDIT_METRIC_A,
        AUDIT_METRIC_B,
        METRIC_A_P50_MS,
        METRIC_A_P95_MS,
        METRIC_B_P50_MS,
        METRIC_B_P95_MS,
    )
    from qa_signal_audit import write_platform_signal

    from supabase import create_client

    expected = {
        "metric_a": {"p50": METRIC_A_P50_MS, "p95": METRIC_A_P95_MS},
        "metric_b": {"p50": METRIC_B_P50_MS, "p95": METRIC_B_P95_MS},
    }
    if TARGETS != expected:
        raise SystemExit(f"TARGETS drifted from app.services.voice_slo: {TARGETS} != {expected}")

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    since = (datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)).isoformat()
    scope_org = (env.get("VOICE_SLO_ALERT_ORG_ID") or "").strip() or None

    def _rows(action: str, org_id: str | None) -> list[dict[str, Any]]:
        q = sb.table("audit_events").select("metadata,created_at").eq("action", action)
        if org_id:
            q = q.eq("org_id", org_id)
        return q.gte("created_at", since).order("created_at", desc=True).limit(500).execute().data or []

    all_orgs = summarize(
        samples_ms(_rows(AUDIT_METRIC_A, None)),
        samples_ms(_rows(AUDIT_METRIC_B, None)),
        label="all_orgs",
        min_samples=MIN_SAMPLES,
    )
    scoped = None
    if scope_org:
        scoped = summarize(
            samples_ms(_rows(AUDIT_METRIC_A, scope_org)),
            samples_ms(_rows(AUDIT_METRIC_B, scope_org)),
            label=f"org:{scope_org}",
            min_samples=MIN_SAMPLES,
        )
    report = build_report(all_orgs, scoped, window_hours=WINDOW_HOURS, min_samples=MIN_SAMPLES)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["verdict"] == "ALERT":
        write_platform_signal(
            sb,
            action="platform.voice_slo.alert",
            verdict=f"ALERT — {'; '.join(report['alerts'])}",
            metadata=report,
        )
        return 1
    if report["verdict"] == "NO_DATA":
        print(
            f"NO_DATA: fewer than {MIN_SAMPLES} samples in "
            f"{', '.join(report['insufficient_samples'])} ({report['judged_scope']}); not a pass",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
