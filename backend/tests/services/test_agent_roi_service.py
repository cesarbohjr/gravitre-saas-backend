"""Unit tests for agent ROI honesty + computation."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.agent_roi_service import (
    DEFAULT_LABOR_USD_PER_HOUR,
    build_agent_roi_report,
    compute_psa_comparison,
    estimate_hours_for_job,
    extract_revenue_amount,
    resolve_labor_usd_per_hour,
    resolve_psa_baseline,
)


def test_estimate_hours_uses_task_type_default_without_duration():
    est = estimate_hours_for_job({"kind": "operator_task", "status": "completed"})
    assert est["provenance"] == "estimate"
    assert est["method"] == "task_type_default"
    assert est["estimatedHours"] == round(20.0 / 60.0, 4)


def test_estimate_hours_uses_wall_clock_multiplier():
    est = estimate_hours_for_job(
        {
            "kind": "operator_task",
            "started_at": "2026-09-01T10:00:00+00:00",
            "finished_at": "2026-09-01T10:02:00+00:00",
        }
    )
    assert est["method"] == "wall_clock_x_human_multiplier"
    # 2 wall minutes × 5 = 10, but kind default 20 wins via max()
    assert est["estimatedMinutes"] == 20.0


def test_extract_revenue_never_invents():
    assert extract_revenue_amount(None) is None
    assert extract_revenue_amount({}) is None
    assert extract_revenue_amount({"amount_usd": 120.5}) == 120.5
    assert extract_revenue_amount({"amount_usd": 0}) is None


def test_labor_rate_org_override_vs_default():
    rate, source = resolve_labor_usd_per_hour({"roi_labor_usd_per_hour": 60})
    assert rate == 60.0
    assert source == "org_settings"
    rate2, source2 = resolve_labor_usd_per_hour({})
    assert rate2 == DEFAULT_LABOR_USD_PER_HOUR
    assert source2 == "default_estimate"


def test_build_report_labels_measured_vs_estimate():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 30, tzinfo=timezone.utc)
    report = build_agent_roi_report(
        org_id="org-1",
        agents=[{"id": "agent-1", "name": "Sales Ops"}],
        model_call_rows=[
            {"agent_id": "agent-1", "cost_usd": 2.5},
            {"agent_id": "agent-1", "cost_usd": 0.5},
        ],
        job_rows=[
            {
                "status": "completed",
                "kind": "operator_task",
                "payload": {"agent_id": "agent-1"},
                "started_at": "2026-09-02T10:00:00+00:00",
                "finished_at": "2026-09-02T10:01:00+00:00",
            }
        ],
        outcome_rows=[],
        org_settings={},
        period_days=30,
        period_start=start,
        period_end=end,
    )
    agent = report["agents"][0]
    assert agent["agentCostUsd"]["value"] == 3.0
    assert agent["agentCostUsd"]["provenance"] == "measured"
    assert agent["tasksCompleted"]["value"] == 1
    assert agent["tasksCompleted"]["provenance"] == "operational"
    assert agent["estimatedHoursSaved"]["provenance"] == "estimate"
    assert agent["estimatedLaborValueUsd"]["provenance"] == "estimate"
    assert agent["revenueInfluencedUsd"]["provenance"] == "not_configured"
    assert agent["revenueInfluencedUsd"]["value"] is None
    assert agent["roiMultiple"]["value"] is not None
    assert agent["roiMultiple"]["provenance"] == "estimate"
    assert report["orgTotals"]["agentCostUsd"]["value"] == 3.0


def test_revenue_only_when_outcome_has_amount():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 30, tzinfo=timezone.utc)
    report = build_agent_roi_report(
        org_id="org-1",
        agents=[{"id": "agent-1", "name": "Closer"}],
        model_call_rows=[{"agent_id": "agent-1", "cost_usd": 1.0}],
        job_rows=[],
        outcome_rows=[
            {
                "agent_id": "agent-1",
                "outcome_event": "connector_action_executed",
                "metadata": {"amount_usd": 500},
            }
        ],
        org_settings={"roi_labor_usd_per_hour": 50},
        period_days=30,
        period_start=start,
        period_end=end,
    )
    agent = report["agents"][0]
    assert agent["revenueInfluencedUsd"]["value"] == 500.0
    assert agent["revenueInfluencedUsd"]["provenance"] == "measured"
    assert agent["actionsExecuted"]["value"] == 1


def test_report_pagination_reads_beyond_single_rest_page_without_duplicates():
    from types import SimpleNamespace
    from app.services.agent_roi_service import _read_report_pages
    class Query:
        rows = [{"id": str(i)} for i in range(1500)]
        def order(self, *_): return self
        def range(self, start, end): self.start, self.end = start, end; return self
        def execute(self): return SimpleNamespace(data=self.rows[self.start:self.end + 1])
    rows, complete = _read_report_pages(Query())
    assert len(rows) == 1500 and complete


def test_incomplete_cost_evidence_cannot_publish_an_roi_multiple():
    from app.services.agent_roi_service import _apply_report_coverage
    report = build_agent_roi_report(
        org_id="org", agents=[{"id": "a", "name": "A"}],
        model_call_rows=[{"agent_id": "a", "cost_usd": 1}],
        job_rows=[{"status": "completed", "kind": "operator_task", "payload": {"agent_id": "a"}}],
        outcome_rows=[], org_settings={}, period_days=30,
        period_start=datetime(2026, 9, 1, tzinfo=timezone.utc), period_end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    _apply_report_coverage(report, {"model_calls": False, "agent_jobs": True, "outcomes": True})
    assert report["orgTotals"]["agentCostUsd"]["value"] is None
    assert report["orgTotals"]["roiMultiple"]["value"] is None
    assert report["agents"][0]["roiMultiple"]["value"] is None
    assert report["honesty"]["dataComplete"] is False


def test_repeated_page_and_bounded_report_are_labeled_incomplete():
    from types import SimpleNamespace
    from app.services.agent_roi_service import _read_report_pages
    class Query:
        def order(self, *_): return self
        def range(self, *_): return self
        def execute(self): return SimpleNamespace(data=[{"id": "one"}, {"id": "two"}])
    rows, complete = _read_report_pages(Query(), page_size=2)
    assert len(rows) == 2 and not complete
    assert _read_report_pages(Query(), page_size=2, max_rows=2)[1] is False


# ---------------------------------------------------------------------------
# PSA baseline (Row 4 — Release 3)
# ---------------------------------------------------------------------------

def test_resolve_psa_baseline_returns_none_when_not_configured():
    assert resolve_psa_baseline(None) is None
    assert resolve_psa_baseline({}) is None
    assert resolve_psa_baseline({"other_key": 1}) is None
    assert resolve_psa_baseline({"psa_baseline": {}}) is None


def test_resolve_psa_baseline_returns_configured_fields():
    result = resolve_psa_baseline({
        "psa_baseline": {
            "avg_mttr_minutes": 45.0,
            "avg_technician_hours_per_ticket": 0.75,
            "avg_tickets_per_day": 30,
            "baseline_period_label": "Q3 2024 pre-automation",
        }
    })
    assert result is not None
    assert result["avg_mttr_minutes"] == 45.0
    assert result["avg_technician_hours_per_ticket"] == 0.75
    assert result["avg_tickets_per_day"] == 30
    assert result["baseline_period_label"] == "Q3 2024 pre-automation"


def test_resolve_psa_baseline_partial_config_is_valid():
    """Org only configured MTTR — partial baseline is still useful."""
    result = resolve_psa_baseline({"psa_baseline": {"avg_mttr_minutes": 60.0}})
    assert result is not None
    assert result["avg_mttr_minutes"] == 60.0
    assert "avg_technician_hours_per_ticket" not in result


def test_compute_psa_comparison_unconfigured():
    result = compute_psa_comparison(None, [], 45.0)
    assert result["configured"] is False
    assert "note" in result
    assert "psa_baseline" in result["note"].lower() or "baseline" in result["note"].lower()


def test_compute_psa_comparison_no_resolution_events():
    """Baseline configured but no measured resolution events → measured=None, no delta."""
    baseline = {"avg_mttr_minutes": 45.0, "avg_tickets_per_day": 20}
    result = compute_psa_comparison(baseline, [], 45.0)
    assert result["configured"] is True
    assert result["measured"] is None
    assert result["delta"] is None
    assert "avg_mttr_minutes" in result["baseline"]
    # Provenance should be org_settings
    assert result["baseline"]["avg_mttr_minutes"]["provenance"] == "org_settings"


def test_compute_psa_comparison_with_measured_resolution_events():
    """Resolution events with resolution_time_minutes → measured MTTR computed."""
    baseline = {"avg_mttr_minutes": 60.0}
    outcome_rows = [
        {"outcome_event": "ticket_resolved", "metadata": {"resolution_time_minutes": 30.0}},
        {"outcome_event": "ticket_resolved", "metadata": {"resolution_time_minutes": 20.0}},
    ]
    result = compute_psa_comparison(baseline, outcome_rows, 45.0)
    assert result["configured"] is True
    assert result["measured"] is not None
    assert result["measured"]["avg_mttr_minutes"]["value"] == 25.0  # (30+20)/2
    assert result["measured"]["avg_mttr_minutes"]["provenance"] == "measured"
    assert result["measured"]["resolution_event_count"] == 2


def test_compute_psa_comparison_delta_positive_when_faster():
    """Baseline 60 min, measured 25 min → delta = 35 min improvement."""
    baseline = {"avg_mttr_minutes": 60.0}
    outcome_rows = [
        {"outcome_event": "ticket_resolved", "metadata": {"resolution_time_minutes": 25.0}},
    ]
    result = compute_psa_comparison(baseline, outcome_rows, 60.0)
    assert result["delta"] is not None
    assert result["delta"]["mttrDeltaMinutes"]["value"] == 35.0
    assert result["delta"]["mttrDeltaMinutes"]["provenance"] == "estimate"
    # labor saved: 35 min / 60 * $60/hr = $35
    assert result["delta"]["laborSavedPerTicketUsd"]["value"] == 35.0


def test_compute_psa_comparison_ignores_non_resolution_events():
    """Other outcome events are not counted as resolution time measurements."""
    baseline = {"avg_mttr_minutes": 60.0}
    outcome_rows = [
        {"outcome_event": "ticket_intake_completed", "metadata": {"resolution_time_minutes": 999.0}},
        {"outcome_event": "connector_action_executed", "metadata": {"resolution_time_minutes": 1.0}},
    ]
    result = compute_psa_comparison(baseline, outcome_rows, 45.0)
    assert result["measured"] is None
    assert result["delta"] is None


def test_compute_psa_comparison_alternate_time_keys():
    """time_to_resolve_minutes and mttr_minutes are also accepted."""
    baseline = {"avg_mttr_minutes": 45.0}
    outcome_rows = [
        {"outcome_event": "ticket_closed", "metadata": {"time_to_resolve_minutes": 20.0}},
        {"outcome_event": "ticket_closed", "metadata": {"mttr_minutes": 30.0}},
    ]
    result = compute_psa_comparison(baseline, outcome_rows, 45.0)
    assert result["measured"]["resolution_event_count"] == 2


def test_build_report_includes_psa_baseline_section():
    """build_agent_roi_report always includes psaBaseline key."""
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 30, tzinfo=timezone.utc)
    report = build_agent_roi_report(
        org_id="org-1",
        agents=[{"id": "a1", "name": "Agent 1"}],
        model_call_rows=[{"agent_id": "a1", "cost_usd": 0.5}],
        job_rows=[],
        outcome_rows=[],
        org_settings={},
        period_days=30,
        period_start=start,
        period_end=end,
    )
    assert "psaBaseline" in report
    assert report["psaBaseline"]["configured"] is False


def test_build_report_psa_baseline_with_configured_baseline():
    """When org_settings has psa_baseline, psaBaseline.configured is True."""
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 30, tzinfo=timezone.utc)
    report = build_agent_roi_report(
        org_id="org-1",
        agents=[{"id": "a1", "name": "Agent 1"}],
        model_call_rows=[{"agent_id": "a1", "cost_usd": 0.5}],
        job_rows=[],
        outcome_rows=[
            {"outcome_event": "ticket_resolved", "metadata": {"resolution_time_minutes": 20.0}}
        ],
        org_settings={"psa_baseline": {"avg_mttr_minutes": 60.0}, "roi_labor_usd_per_hour": 60.0},
        period_days=30,
        period_start=start,
        period_end=end,
    )
    psa = report["psaBaseline"]
    assert psa["configured"] is True
    assert psa["baseline"]["avg_mttr_minutes"]["value"] == 60.0
    assert psa["measured"]["avg_mttr_minutes"]["value"] == 20.0
    assert psa["delta"]["mttrDeltaMinutes"]["value"] == 40.0


def test_freshservice_time_entries_in_action_catalog():
    """freshservice.tickets.time_entries action is registered in the enrichment catalog."""
    from app.connectors.action_catalog.action_retrieval_enrichment import ACTION_RETRIEVAL_ENRICHMENT
    assert "freshservice.tickets.time_entries" in ACTION_RETRIEVAL_ENRICHMENT
    entry = ACTION_RETRIEVAL_ENRICHMENT["freshservice.tickets.time_entries"]
    assert "psa" in entry["tags"] or "time-entries" in entry["tags"]
    assert len(entry["examples"]) >= 1
