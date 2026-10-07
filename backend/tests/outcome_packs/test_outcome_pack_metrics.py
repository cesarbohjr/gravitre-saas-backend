"""Business metrics and Play impact come only from counted, verified results."""
from __future__ import annotations

from app.outcome_packs.memory_store import MemoryStore
from app.plays.impact import play_impact_summary
from app.services.business_metrics_service import business_metric_evidence, compute_business_metrics

ORG = "00000000-0000-4000-8000-0000000000c3"


def _row(store, metric, *, delta=None, after=None, counted=True, state="VERIFIED SUCCESS", unit="count", currency=None, play="p1"):
    store.table("intelligence_outcome_events").insert({
        "org_id": ORG, "outcome_event": "play_business_result", "after_value": after, "before_value": 0,
        "created_at": "2099-01-01T00:00:00+00:00", "measured_at": "2099-01-01T00:00:00+00:00",
        "metadata": {"metric_key": metric, "delta_value": delta, "unit": unit, "currency": currency, "play_key": play,
                     "verification_state": state, "counted_in_total": counted, "claim_key": f"{metric}|{delta}|{after}|{counted}|{currency}"},
    }).execute()


def _value(store, key):
    return next(m for m in compute_business_metrics(store, ORG, range_key="all", metric_keys=[key])["metrics"])


def test_no_evidence_is_unknown_not_zero():
    row = _value(MemoryStore(), "qualified_leads")
    assert row["value"] is None and row["status"] == "no_verified_evidence"
    assert _value(MemoryStore(), "not_a_metric")["status"] == "not_defined"


def test_assisted_results_never_add():
    store = MemoryStore()
    _row(store, "qualified_leads", delta=1)
    _row(store, "qualified_leads", delta=1, counted=False)
    _row(store, "qualified_leads", delta=1, state="ACTIONED")
    row = _value(store, "qualified_leads")
    assert row["value"] == 1 and row["assistedResultCount"] == 1


def test_avg_metric_averages_measured_value():
    store = MemoryStore()
    _row(store, "sales_cycle_days", delta=-5, after=30, unit="days")
    _row(store, "sales_cycle_days", delta=-5, after=40, unit="days")
    assert _value(store, "sales_cycle_days")["value"] == 35
    impact = play_impact_summary(store, ORG)
    assert impact["verifiedMetrics"][0]["value"] == 35


def test_mixed_currency_is_insufficient():
    store = MemoryStore()
    _row(store, "won_revenue", delta=100, unit="currency", currency="USD")
    _row(store, "won_revenue", delta=100, unit="currency", currency="EUR")
    assert _value(store, "won_revenue")["status"] == "insufficient_data"


def test_ratio_needs_both_sides():
    store = MemoryStore()
    _row(store, "deals_won", delta=1)
    assert _value(store, "opportunity_to_won_conversion")["value"] is None
    _row(store, "opportunities_created", delta=4)
    assert _value(store, "opportunity_to_won_conversion")["status"] == "verified"


def test_evidence_lists_contributions_and_exceptions():
    store = MemoryStore()
    _row(store, "qualified_leads", delta=1)
    _row(store, "qualified_leads", state="VERIFIED FAILURE")
    out = business_metric_evidence(store, ORG, "qualified_leads", range_key="all")
    assert len(out["contributions"]) == 1 and out["contributions"][0]["evidenceHref"].startswith("/plays/p1/results/")
    assert out["exceptions"][0]["kind"] == "verified_failure"
