"""3.0-C voice baseline and lane comparison wiring."""
from __future__ import annotations

from app.services.voice_realtime_eval import LANE_A, LANE_B, lane_comparison
from app.services.voice_slo import METRIC_A_P50_MS, METRIC_A_P95_MS


def _metric_a_pass(p50: int | None, p95: int | None) -> bool:
    if p50 is None or p95 is None:
        return False
    return p50 < METRIC_A_P50_MS and p95 < METRIC_A_P95_MS


def test_metric_a_pass_requires_both_p50_and_p95() -> None:
    assert _metric_a_pass(400, 700) is True
    assert _metric_a_pass(600, 700) is False
    assert _metric_a_pass(400, 900) is False


def test_compare_vs_3_0_a_delta() -> None:
    from pathlib import Path

    import json
    import sys

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "scripts"))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "aggregate_3_0_c",
        root / "scripts" / "aggregate-3.0-c-voice-baseline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    frozen = json.loads((root / "docs" / "delivery" / "3.0-a-voice-probe-frozen.json").read_text())
    result = mod.compare_vs_3_0_a(
        {"p50_ms": 648, "p95_ms": 10029},
        {"p50_ms": 46080, "p95_ms": 62527},
    )
    assert result["status"] == "COMPARED"
    assert result["metric_a"]["delta_p50_ms"] == 648 - frozen["metric_a"]["p50_ms"]
    assert result["metric_a"]["not_worse_p95"] is False


def test_lane_comparison_wires_measured_lane_a_only() -> None:
    measured_a = {
        "latency_metric_a": {"p50_ms": 648, "p95_ms": 10029},
        "latency_metric_b": {"p50_ms": 46080, "p95_ms": 62527},
    }
    table = lane_comparison(measured={LANE_A: measured_a})
    assert table["lanes"][LANE_A]["measured"] is True
    assert table["lanes"][LANE_B]["scores"] == "NOT_RUN"
    assert table["production_recommendation"] == LANE_A
