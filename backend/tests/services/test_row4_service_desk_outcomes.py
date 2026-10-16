"""Row 4 — Service-desk outcomes / agent ROI: PSA baseline and cost attribution.

Coverage checklist (Row 4 acceptance criteria):
  - Ticket-outcome telemetry and closed-loop verification
  - Pre/post PSA comparison with configured baseline
  - Per-run cost attribution with model-call evidence
  - Labor-rate source-of-truth (org override vs default)

Tests:
  1.  resolve_psa_baseline returns None when org_settings has no 'psa_baseline' key
  2.  resolve_psa_baseline returns None when psa_baseline is empty dict
  3.  resolve_psa_baseline returns None when org_settings is None
  4.  resolve_psa_baseline returns dict with configured fields when set
  5.  resolve_psa_baseline omits fields not present in baseline dict
  6.  resolve_labor_usd_per_hour returns (45.0, 'default_estimate') when no override
  7.  resolve_labor_usd_per_hour returns (45.0, 'default_estimate') when org_settings is None
  8.  resolve_labor_usd_per_hour returns org rate when roi_labor_usd_per_hour is set
  9.  resolve_labor_usd_per_hour returns org rate when labor_usd_per_hour is set (alias)
  10. resolve_labor_usd_per_hour ignores non-positive org rate (falls back to default)
  11. DEFAULT_LABOR_USD_PER_HOUR is 45.0
  12. run_cost_summary returns None for unknown run_id
  13. run_cost_summary returns dict with model.cost_usd for known run
  14. run_cost_summary result contains expected model keys
  15. compute_psa_comparison returns comparison dict when baseline is provided
  16. build_agent_roi_report returns dict with expected top-level keys
  17. build_agent_roi_report does not raise with empty rows
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest


# ---------------------------------------------------------------------------
# resolve_psa_baseline — configured vs unconfigured branches
# ---------------------------------------------------------------------------

class TestResolvePsaBaseline:
    def test_returns_none_when_no_psa_baseline_key(self):
        """org_settings without 'psa_baseline' key → None."""
        from app.services.agent_roi_service import resolve_psa_baseline

        result = resolve_psa_baseline({"some_other_key": "value"})
        assert result is None

    def test_returns_none_for_empty_dict(self):
        """psa_baseline present but empty dict → None."""
        from app.services.agent_roi_service import resolve_psa_baseline

        result = resolve_psa_baseline({"psa_baseline": {}})
        assert result is None

    def test_returns_none_when_org_settings_is_none(self):
        """org_settings=None → None (no crash)."""
        from app.services.agent_roi_service import resolve_psa_baseline

        result = resolve_psa_baseline(None)
        assert result is None

    def test_returns_dict_with_configured_fields(self):
        """When psa_baseline is populated, configured fields are returned."""
        from app.services.agent_roi_service import resolve_psa_baseline

        org_settings = {
            "psa_baseline": {
                "avg_mttr_minutes": 240,
                "avg_tickets_per_day": 50,
            }
        }
        result = resolve_psa_baseline(org_settings)
        assert result is not None
        assert result["avg_mttr_minutes"] == 240
        assert result["avg_tickets_per_day"] == 50

    def test_omits_fields_not_in_baseline(self):
        """Fields not configured in baseline are absent from result (not set to zero)."""
        from app.services.agent_roi_service import resolve_psa_baseline

        org_settings = {
            "psa_baseline": {
                "avg_mttr_minutes": 180,
                # avg_technician_hours_per_ticket deliberately absent
            }
        }
        result = resolve_psa_baseline(org_settings)
        assert result is not None
        assert "avg_mttr_minutes" in result
        assert "avg_technician_hours_per_ticket" not in result


# ---------------------------------------------------------------------------
# resolve_labor_usd_per_hour — org override vs DEFAULT_LABOR_USD_PER_HOUR
# ---------------------------------------------------------------------------

class TestResolveLaborRate:
    def test_default_when_no_override(self):
        """No org override → (45.0, 'default_estimate')."""
        from app.services.agent_roi_service import resolve_labor_usd_per_hour

        rate, source = resolve_labor_usd_per_hour({})
        assert rate == 45.0
        assert source == "default_estimate"

    def test_default_when_org_settings_none(self):
        """org_settings=None → (45.0, 'default_estimate')."""
        from app.services.agent_roi_service import resolve_labor_usd_per_hour

        rate, source = resolve_labor_usd_per_hour(None)
        assert rate == 45.0
        assert source == "default_estimate"

    def test_org_rate_via_roi_labor_key(self):
        """roi_labor_usd_per_hour in org_settings → that rate, source='org_settings'."""
        from app.services.agent_roi_service import resolve_labor_usd_per_hour

        rate, source = resolve_labor_usd_per_hour({"roi_labor_usd_per_hour": 75.0})
        assert rate == 75.0
        assert source == "org_settings"

    def test_org_rate_via_labor_alias_key(self):
        """labor_usd_per_hour (alias) in org_settings → that rate, source='org_settings'."""
        from app.services.agent_roi_service import resolve_labor_usd_per_hour

        rate, source = resolve_labor_usd_per_hour({"labor_usd_per_hour": 60.0})
        assert rate == 60.0
        assert source == "org_settings"

    def test_ignores_non_positive_org_rate(self):
        """org rate ≤ 0 → falls back to default (guards against bad config)."""
        from app.services.agent_roi_service import resolve_labor_usd_per_hour

        rate, source = resolve_labor_usd_per_hour({"roi_labor_usd_per_hour": 0})
        assert rate == 45.0
        assert source == "default_estimate"

    def test_default_labor_constant_value(self):
        """DEFAULT_LABOR_USD_PER_HOUR is exactly 45.0."""
        from app.services.agent_roi_service import DEFAULT_LABOR_USD_PER_HOUR

        assert DEFAULT_LABOR_USD_PER_HOUR == 45.0


# ---------------------------------------------------------------------------
# run_cost_summary — per-run actual cost evidence
# ---------------------------------------------------------------------------

def _cost_client_none():
    """Supabase client that returns no rows (unknown run)."""
    client = MagicMock()
    empty = MagicMock()
    empty.data = []
    chain = MagicMock()
    chain.eq.return_value = chain
    chain.limit.return_value = MagicMock(execute=MagicMock(return_value=empty))
    client.table.return_value = MagicMock(select=MagicMock(return_value=chain))
    return client


def _cost_client_with_run():
    """Supabase client that returns a workflow_run row with joined model data."""
    client = MagicMock()

    run_row = MagicMock()
    run_row.data = [{"id": "run-1", "org_id": "org-1", "status": "completed"}]
    run_chain = MagicMock()
    run_chain.eq.return_value = run_chain
    run_chain.limit.return_value = MagicMock(execute=MagicMock(return_value=run_row))

    step_row = MagicMock()
    step_row.data = [{"id": "step-1", "run_id": "run-1"}]
    step_chain = MagicMock()
    step_chain.eq.return_value = step_chain
    step_chain.execute.return_value = step_row

    model_row = MagicMock()
    model_row.data = [
        {
            "id": "mc-1",
            "run_id": "run-1",
            "step_id": "step-1",
            "cost_usd": 0.0042,
            "input_tokens": 800,
            "output_tokens": 200,
            "attributed": True,
        }
    ]
    model_chain = MagicMock()
    model_chain.eq.return_value = model_chain
    model_chain.execute.return_value = model_row

    def table_dispatch(table_name):
        if table_name == "workflow_runs":
            return MagicMock(select=MagicMock(return_value=run_chain))
        if table_name == "workflow_steps":
            return MagicMock(select=MagicMock(return_value=step_chain))
        if table_name == "model_calls":
            return MagicMock(select=MagicMock(return_value=model_chain))
        return MagicMock()

    client.table.side_effect = table_dispatch
    return client


class TestRunCostSummary:
    def test_returns_none_for_unknown_run(self):
        """run_cost_summary returns None when no workflow_run row found."""
        from app.services.run_cost_summary import run_cost_summary

        result = run_cost_summary(_cost_client_none(), org_id="org-1", run_id="unknown-run")
        assert result is None

    def test_returns_dict_with_model_cost_for_known_run(self):
        """run_cost_summary returns a dict with model.cost_usd for a known run."""
        from app.services.run_cost_summary import run_cost_summary

        result = run_cost_summary(_cost_client_with_run(), org_id="org-1", run_id="run-1")
        assert result is not None
        assert "model" in result
        assert "cost_usd" in result["model"]

    def test_result_contains_expected_model_keys(self):
        """Result model sub-dict has calls, input_tokens, output_tokens, cost_usd, attributed."""
        from app.services.run_cost_summary import run_cost_summary

        result = run_cost_summary(_cost_client_with_run(), org_id="org-1", run_id="run-1")
        assert result is not None
        model = result["model"]
        for key in ("calls", "input_tokens", "output_tokens", "cost_usd", "attributed"):
            assert key in model, f"Expected key '{key}' in model summary"


# ---------------------------------------------------------------------------
# compute_psa_comparison — baseline vs actual
# ---------------------------------------------------------------------------

class TestComputePsaComparison:
    def test_returns_comparison_dict_with_baseline(self):
        """compute_psa_comparison(baseline, rows, rate) returns a dict."""
        from app.services.agent_roi_service import compute_psa_comparison

        baseline = {"avg_resolution_hours": 4.0, "ticket_volume_per_month": 100}
        outcome_rows: list = []
        result = compute_psa_comparison(baseline, outcome_rows, labor_rate=45.0)
        assert isinstance(result, dict)

    def test_handles_none_baseline_gracefully(self):
        """compute_psa_comparison with None baseline → no crash, returns dict."""
        from app.services.agent_roi_service import compute_psa_comparison

        result = compute_psa_comparison(None, [], labor_rate=45.0)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# build_agent_roi_report — top-level report structure
# ---------------------------------------------------------------------------

class TestBuildAgentRoiReport:
    def _make_report(self, org_settings=None):
        from app.services.agent_roi_service import build_agent_roi_report
        from datetime import date

        return build_agent_roi_report(
            org_id="org-1",
            agents=[],
            model_call_rows=[],
            job_rows=[],
            outcome_rows=[],
            org_settings=org_settings or {},
            period_days=30,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
        )

    def test_returns_dict(self):
        """build_agent_roi_report always returns a dict."""
        result = self._make_report()
        assert isinstance(result, dict)

    def test_does_not_raise_with_empty_rows(self):
        """Empty row sets → no exception."""
        self._make_report()  # must not raise

    def test_report_has_org_id(self):
        """Report includes org_id (or orgId) for traceability."""
        result = self._make_report()
        has_org = result.get("org_id") == "org-1" or result.get("orgId") == "org-1"
        assert has_org, f"Expected org_id or orgId='org-1' in {list(result.keys())}"

    def test_report_includes_labor_rate(self):
        """Report includes a labor rate key."""
        result = self._make_report()
        # accepts snake_case or camelCase naming
        has_labor = any(
            k in result for k in (
                "labor_rate_usd_per_hour", "labor_usd_per_hour", "labor",
                "laborRateUsdPerHour", "laborUsdPerHour",
            )
        )
        assert has_labor, f"Expected labor key in report keys: {list(result.keys())}"
