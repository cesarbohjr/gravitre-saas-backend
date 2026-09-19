"""3.0-A critical-path baseline aggregation."""
from __future__ import annotations

from app.services.turn_latency_baseline import aggregate_critical_path_rows, aggregate_slo_metric_rows


def test_aggregate_critical_path_rows_percentiles_and_stages() -> None:
    rows = [
        {
            "metadata": {
                "total_ms": 1000,
                "dominant_ms": 600,
                "dominant_stage": "CONTEXT_BUILD",
                "spoken_mode": False,
                "stages": [
                    {"stage": "NETWORK", "delta_ms": 50},
                    {"stage": "CONTEXT_BUILD", "delta_ms": 600},
                    {"stage": "COMPOSER", "delta_ms": 350},
                ],
            }
        },
        {
            "metadata": {
                "total_ms": 800,
                "dominant_ms": 400,
                "dominant_stage": "MODEL_TTFT",
                "spoken_mode": False,
                "stages": [
                    {"stage": "NETWORK", "delta_ms": 40},
                    {"stage": "MODEL_TTFT", "delta_ms": 400},
                    {"stage": "COMPOSER", "delta_ms": 360},
                ],
            }
        },
    ]
    out = aggregate_critical_path_rows(rows)
    assert out["sample_count"] == 2
    assert out["turn_total_ms"]["p50_ms"] == 800
    assert out["dominant_delta_ms"]["p50_ms"] == 400
    assert out["by_dominant_stage"]["CONTEXT_BUILD"]["win_count"] == 1
    assert out["by_dominant_stage"]["MODEL_TTFT"]["win_count"] == 1
    assert out["by_stage_delta_ms"]["NETWORK"]["sample_count"] == 2


def test_aggregate_slo_metric_rows() -> None:
    rows = [{"metadata": {"ms": 400}}, {"metadata": {"ms": 800}}]
    out = aggregate_slo_metric_rows(rows)
    assert out["sample_count"] == 2
    assert out["p50_ms"] == 400
