"""Phase 5 — reporting / insights honesty helpers."""
from __future__ import annotations

from app.services.reporting_honesty import (
    REPORTING_SURFACES,
    assess_metric_series,
    label_placeholder_metric,
    normalize_agent_success_rate,
)


def test_inventory_covers_required_surfaces():
    ids = {s["id"] for s in REPORTING_SURFACES}
    assert "activity_outcomes" in ids
    assert "metrics_ops" in ids
    assert "intelligence_reports" in ids
    assert "agents_hub" in ids
    assert "golden_signals" in ids
    assert "built_in_models" in ids
    assert "enterprise_agent_roi" in ids


def test_normalize_never_defaults_100_without_runs():
    out = normalize_agent_success_rate(stored_rate=None, total_runs=0)
    assert out["success_rate"] is None
    assert out["provenance"] == "insufficient_data"


def test_normalize_prefers_live_outcomes():
    out = normalize_agent_success_rate(
        stored_rate=94,
        total_runs=12,
        live_outcome={"status": "ok", "score": 0.8, "events_count": 10},
    )
    assert out["success_rate"] == 80.0
    assert out["provenance"] == "live_outcomes"


def test_static_series_flagged():
    result = assess_metric_series([72.0, 72.0, 72.0, 72.0, 72.0], metric_name="success_rate")
    assert result["flagged"] is True
    assert result["reason"] == "static_value_dominance"
    assert result["failure_class"] == "degenerate_report_metric"


def test_varied_series_ok():
    result = assess_metric_series([40.0, 55.0, 70.0, 62.0, 80.0], metric_name="success_rate")
    assert result["flagged"] is False
    assert result["reason"] == "ok_variance"


def test_roi_placeholder_helper_still_honest():
    card = label_placeholder_metric("Legacy placeholder")
    assert card["value"] is None
    assert card["provenance"] == "not_configured"
