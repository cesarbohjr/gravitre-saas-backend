"""Phase 4 — statistical degenerate / low-info batch detector."""
from __future__ import annotations

from app.services.batch_degeneracy import (
    BATCH_CLASS_THRESHOLDS,
    apply_batch_degeneracy_to_status,
    assess_batch_degeneracy,
)


def test_cmumulle72_six_identical_schema_valid_rows_flagged():
    """Standing regression: 6 schema-valid rows, all identical worthless values."""
    records = [
        {
            "name": "Acme Corp",
            "industry": "cannot tell",
            "employee_count": "N/A",
            "fit_score": "unknown",
        }
        for _ in range(6)
    ]
    result = assess_batch_degeneracy(
        {"records": records},
        invoke_action="clay.enrich",
    )
    assert result.flagged is True
    assert result.record_count == 6
    assert result.reason in {"identical_value_dominance", "placeholder_dominance"}
    status, deg = apply_batch_degeneracy_to_status(
        status="completed",
        invoke_action="clay.enrich",
        result_data={"records": records},
    )
    assert status == "flagged_for_review"
    assert deg and deg.flagged


def test_varied_enrichment_batch_passes():
    records = [
        {"name": "Acme", "industry": "SaaS", "employee_count": "50"},
        {"name": "Beta LLC", "industry": "Healthcare", "employee_count": "200"},
        {"name": "Gamma Inc", "industry": "Finance", "employee_count": "1200"},
        {"name": "Delta Co", "industry": "Retail", "employee_count": "30"},
        {"name": "Echo GmbH", "industry": "Manufacturing", "employee_count": "800"},
        {"name": "Foxtrot Ltd", "industry": "Education", "employee_count": "90"},
    ]
    result = assess_batch_degeneracy({"contacts": records}, invoke_action="apollo.people.enrich")
    assert result.flagged is False
    assert result.reason == "ok_variance"


def test_placeholder_majority_flagged():
    records = [
        {"title": "N/A", "notes": "cannot tell"},
        {"title": "n/a", "notes": "unknown"},
        {"title": "N/A", "notes": "N/A"},
        {"title": "unknown", "notes": "cannot tell"},
    ]
    result = assess_batch_degeneracy({"results": records}, invoke_action="hubspot.contacts.create")
    assert result.flagged is True
    assert result.reason == "placeholder_dominance"


def test_small_batch_skipped():
    records = [
        {"name": "A", "industry": "SaaS"},
        {"name": "A", "industry": "SaaS"},
    ]
    result = assess_batch_degeneracy({"records": records})
    assert result.flagged is False
    assert result.reason == "batch_too_small"


def test_thresholds_documented_per_class():
    assert set(BATCH_CLASS_THRESHOLDS) >= {"enrichment", "list_population", "default"}
    for cfg in BATCH_CLASS_THRESHOLDS.values():
        assert 0.5 <= float(cfg["identical_ratio"]) <= 0.95
        assert 0.4 <= float(cfg["placeholder_ratio"]) <= 0.8
        assert int(cfg["min_batch"]) >= 3


def test_does_not_upgrade_failed():
    status, deg = apply_batch_degeneracy_to_status(
        status="failed",
        invoke_action="clay.enrich",
        result_data={"records": [{"x": "1"}] * 6},
    )
    assert status == "failed"
