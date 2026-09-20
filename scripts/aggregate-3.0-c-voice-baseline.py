#!/usr/bin/env python3
"""Publish 3.0-C lane-A voice baseline from live Metric A/B probe + lane comparison.

Reads docs/delivery/voice-slo-two-metric-live.json (from verify-voice-slo-two-metric-live.py)
and writes docs/delivery/3.0-c-voice-baseline-latest.json with lane_comparison measured
scores for A_CASCADE only. Does not claim SLO PASS.

Usage:
  python scripts/verify-voice-slo-two-metric-live.py
  python scripts/aggregate-3.0-c-voice-baseline.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))

from app.services.voice_realtime_eval import LANE_A, lane_comparison  # noqa: E402
from app.services.voice_slo import (  # noqa: E402
    METRIC_A_P50_MS,
    METRIC_A_P95_MS,
    METRIC_B_P50_MS,
    METRIC_B_P95_MS,
)

DEFAULT_PROBE = ROOT / "docs" / "delivery" / "voice-slo-two-metric-live.json"
DEFAULT_OUT = ROOT / "docs" / "delivery" / "3.0-c-voice-baseline-latest.json"
FROZEN_3_0_A = ROOT / "docs" / "delivery" / "3.0-a-voice-probe-frozen.json"
LIVE_API = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")


def load_env() -> None:
    for path in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                for k, v in dotenv_values(path, encoding=enc).items():
                    if v and k not in os.environ:
                        os.environ[k] = v
                break
            except UnicodeDecodeError:
                continue


def fetch_health() -> dict[str, Any]:
    try:
        resp = httpx.get(f"{LIVE_API}/health", timeout=20.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}


def metric_a_pass(p50: int | None, p95: int | None) -> bool:
    if p50 is None or p95 is None:
        return False
    return p50 < METRIC_A_P50_MS and p95 < METRIC_A_P95_MS


def metric_b_pass(p50: int | None, p95: int | None) -> bool:
    if p50 is None or p95 is None:
        return False
    return p50 < METRIC_B_P50_MS and p95 < METRIC_B_P95_MS


def _delta(current: int | None, baseline: int | None) -> int | None:
    if current is None or baseline is None:
        return None
    return int(current) - int(baseline)


def compare_vs_3_0_a(
    metric_a: dict[str, Any],
    metric_b: dict[str, Any],
    frozen_path: Path = FROZEN_3_0_A,
) -> dict[str, Any]:
    """Document delta vs frozen 3.0-A HTTP Talk probe — no PASS claim."""
    if not frozen_path.is_file():
        return {"status": "NOT_RUN", "reason": f"missing {frozen_path}"}
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    fa = frozen.get("metric_a") or {}
    fb = frozen.get("metric_b") or {}
    a_p50 = metric_a.get("p50_ms")
    a_p95 = metric_a.get("p95_ms")
    b_p50 = metric_b.get("p50_ms")
    b_p95 = metric_b.get("p95_ms")
    return {
        "status": "COMPARED",
        "frozen_source": str(frozen_path),
        "frozen_git_sha": frozen.get("git_sha"),
        "metric_a": {
            "baseline_p50_ms": fa.get("p50_ms"),
            "baseline_p95_ms": fa.get("p95_ms"),
            "current_p50_ms": a_p50,
            "current_p95_ms": a_p95,
            "delta_p50_ms": _delta(a_p50, fa.get("p50_ms")),
            "delta_p95_ms": _delta(a_p95, fa.get("p95_ms")),
            "not_worse_p50": a_p50 is not None and fa.get("p50_ms") is not None and a_p50 <= fa.get("p50_ms"),
            "not_worse_p95": a_p95 is not None and fa.get("p95_ms") is not None and a_p95 <= fa.get("p95_ms"),
        },
        "metric_b": {
            "baseline_p50_ms": fb.get("p50_ms"),
            "baseline_p95_ms": fb.get("p95_ms"),
            "current_p50_ms": b_p50,
            "current_p95_ms": b_p95,
            "delta_p50_ms": _delta(b_p50, fb.get("p50_ms")),
            "delta_p95_ms": _delta(b_p95, fb.get("p95_ms")),
        },
        "note": "Delta only; 3.0-C gate uses P95 not-worse vs frozen 3.0-A probe.",
    }


def build_report(probe_path: Path) -> dict[str, Any]:
    load_env()
    health = fetch_health()
    probe: dict[str, Any] = {}
    if probe_path.is_file():
        probe = json.loads(probe_path.read_text(encoding="utf-8"))

    metric_a = probe.get("metric_a") or {}
    metric_b = probe.get("metric_b") or {}
    a_p50 = metric_a.get("p50_ms")
    a_p95 = metric_a.get("p95_ms")
    b_p50 = metric_b.get("p50_ms")
    b_p95 = metric_b.get("p95_ms")

    measured_a = {
        "latency_metric_a": {"p50_ms": a_p50, "p95_ms": a_p95, "samples": metric_a.get("samples")},
        "latency_metric_b": {"p50_ms": b_p50, "p95_ms": b_p95, "samples": metric_b.get("samples")},
        "probe_verdict": probe.get("verdict"),
        "probe_git_sha": (probe.get("health") or {}).get("git_sha"),
        "probe_generated_at": probe.get("generated_at"),
        "conversation_ids": probe.get("conversation_ids"),
    }

    comparison = lane_comparison(measured={LANE_A: measured_a})
    vs_3_0_a = compare_vs_3_0_a(metric_a, metric_b)

    return {
        "probe": "3.0_c_voice_baseline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health": {
            "git_sha": health.get("git_sha"),
            "status": health.get("status"),
            "timestamp": health.get("timestamp"),
        },
        "probe_source": str(probe_path),
        "slo_targets": {
            "metric_a": {"p50_ms": METRIC_A_P50_MS, "p95_ms": METRIC_A_P95_MS},
            "metric_b": {"p50_ms": METRIC_B_P50_MS, "p95_ms": METRIC_B_P95_MS},
        },
        "metric_a_measured": metric_a,
        "metric_b_measured": metric_b,
        "slo_pass": {
            "metric_a": metric_a_pass(
                int(a_p50) if isinstance(a_p50, (int, float)) else None,
                int(a_p95) if isinstance(a_p95, (int, float)) else None,
            ),
            "metric_b": metric_b_pass(
                int(b_p50) if isinstance(b_p50, (int, float)) else None,
                int(b_p95) if isinstance(b_p95, (int, float)) else None,
            ),
        },
        "lane_comparison": comparison,
        "compare_vs_3_0_a": vs_3_0_a,
        "note": (
            "Lane A (cascade) measured from HTTP Talk probe only. Lanes B/C remain NOT_RUN. "
            "slo_pass false is expected until Metric A P95 and Metric B meet published bars."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate 3.0-C voice baseline for lane A")
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE, help="voice-slo probe JSON")
    parser.add_argument("--json", type=Path, default=DEFAULT_OUT, help="Output JSON path")
    args = parser.parse_args()

    if not args.probe.is_file():
        print(json.dumps({"error": f"probe missing: {args.probe}", "run": "verify-voice-slo-two-metric-live.py"}))
        return 2

    report = build_report(args.probe)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.json),
                "sha": report["health"].get("git_sha"),
                "metric_a_pass": report["slo_pass"]["metric_a"],
                "metric_b_pass": report["slo_pass"]["metric_b"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
