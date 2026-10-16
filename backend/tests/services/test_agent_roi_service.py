"""Unit tests for agent ROI honesty + computation."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.agent_roi_service import (
    DEFAULT_LABOR_USD_PER_HOUR,
    build_agent_roi_report,
    estimate_hours_for_job,
    extract_revenue_amount,
    resolve_labor_usd_per_hour,
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
