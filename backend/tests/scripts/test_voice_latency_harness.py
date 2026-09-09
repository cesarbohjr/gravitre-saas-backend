"""The harness must refuse to call noise a result.

Four optimizations this phase were evaluated against single samples in an
environment where retrieval_gather ranged 1,983-49,313ms. These tests pin the
statistics that make that mistake impossible: a change is only reported as
improved or regressed when the bootstrap 95% intervals on the medians do not
overlap.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_HARNESS = (
    Path(__file__).resolve().parents[3] / "scripts" / "measure-voice-latency-harness.py"
)


@pytest.fixture(scope="module")
def harness():
    sys.path.insert(0, str(_HARNESS.parent))
    spec = importlib.util.spec_from_file_location("voice_latency_harness", _HARNESS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestPercentile:
    def test_median_and_p90(self, harness) -> None:
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        assert harness._percentile(vals, 50) == 5.0
        assert harness._percentile(vals, 90) == 9.0

    def test_empty_is_none(self, harness) -> None:
        assert harness._percentile([], 50) is None

    def test_single_value(self, harness) -> None:
        assert harness._percentile([42.0], 90) == 42.0


class TestNoiseFloor:
    def test_tight_data_gives_a_narrow_interval(self, harness) -> None:
        out = harness._median_ci([100.0] * 12)
        assert out["ci95"] == [100.0, 100.0]
        assert out["ci95_width"] == 0.0

    def test_the_observed_production_spread_gives_a_wide_interval(self, harness) -> None:
        # Real retrieval_gather samples from this phase.
        vals = [1983.0, 2503.0, 3156.0, 4084.0, 4115.0, 4391.0, 4669.0, 6901.0, 49313.0]
        out = harness._median_ci(vals)
        # If the interval is not wide, the harness is lying about what 9 samples
        # of this data can resolve.
        assert out["ci95_width"] > 1000, out

    def test_too_few_samples_reports_no_interval(self, harness) -> None:
        assert harness._median_ci([1.0, 2.0])["ci95"] is None

    def test_summarize_exposes_spread(self, harness) -> None:
        out = harness._summarize([1983.0, 49313.0, 4115.0])
        assert out["spread_ratio"] == pytest.approx(24.9, abs=0.2)
        assert out["min"] == 1983.0
        assert out["max"] == 49313.0

    def test_summarize_drops_none(self, harness) -> None:
        assert harness._summarize([None, None])["n"] == 0
        assert harness._summarize([1.0, None, 3.0])["n"] == 2


class TestStageDeltas:
    def test_cumulative_checkpoints_become_per_stage_costs(self, harness) -> None:
        rows = [{"checkpoints": {"a": 100, "b": 350, "c": 400}}]
        assert harness._stage_deltas(rows) == {"a": [100.0], "b": [250.0], "c": [50.0]}

    def test_multiple_turns_accumulate_samples(self, harness) -> None:
        rows = [
            {"checkpoints": {"a": 10, "b": 30}},
            {"checkpoints": {"a": 20, "b": 25}},
        ]
        out = harness._stage_deltas(rows)
        assert out["a"] == [10.0, 20.0]
        assert out["b"] == [20.0, 5.0]

    def test_non_numeric_checkpoints_are_skipped(self, harness) -> None:
        rows = [{"checkpoints": {"a": 10, "bad": "x", "b": 20}}]
        out = harness._stage_deltas(rows)
        assert "bad" not in out
        assert out["b"] == [10.0]


class TestLogParsing:
    def test_matches_a_real_breakdown_line(self, harness) -> None:
        line = (
            "2026-09-09 20:16:18,962 [INFO] app.services.intelligence_orchestrator "
            "request_id= user_id= org_id= prepare_assistant_turn_breakdown_ms "
            "org_id=f07e57c0-1501-4000-8000-c04e57a00001 mode=fast routing_tier=simple "
            "n_rag_sources=5 checkpoints={'connected_integrations': 0, "
            "'knowledge_fabric': 366, 'retrieval_gather': 1896}"
        )
        m = harness._LOG_PATTERNS["prepare_assistant_turn"].search(line)
        assert m is not None
        import ast

        cp = ast.literal_eval(m.group("cp"))
        assert cp["retrieval_gather"] == 1896

    def test_matches_the_context_breakdown_line(self, harness) -> None:
        line = (
            "2026-09-09 16:09:26,191 [INFO] app.operators.agent_intelligence "
            "org_id= agent_intelligence_context_breakdown_ms "
            "org_id=f07e57c0-1501-4000-8000-c04e57a00001 spoken_lite_path=True "
            "checkpoints={'pre_kernel_entry': 202, 'unified_live_resolved': 4143}"
        )
        m = harness._LOG_PATTERNS["agent_intelligence_context"].search(line)
        assert m is not None


class TestComparisonVerdict:
    def _snapshot(self, label, values):
        return {
            "label": label,
            "runs_ok": len(values),
            "runs_attempted": len(values),
            "client": {"first_answer_ms": {"n": len(values)}},
            "server": {},
            "_values": values,
        }

    def test_overlapping_intervals_are_indistinguishable(self, harness, capsys) -> None:
        noisy_a = [2000.0, 3000.0, 4000.0, 5000.0, 20000.0, 4200.0, 3800.0, 4400.0]
        noisy_b = [2100.0, 3100.0, 4100.0, 5100.0, 19000.0, 4300.0, 3900.0, 4500.0]
        sa = harness._median_ci(noisy_a)
        sb = harness._median_ci(noisy_b)
        (alo, ahi), (blo, bhi) = sa["ci95"], sb["ci95"]
        assert alo <= bhi and blo <= ahi, "this pair must read as indistinguishable"

    def test_clearly_separated_data_is_detectable(self, harness) -> None:
        sa = harness._median_ci([5000.0] * 10)
        sb = harness._median_ci([1000.0] * 10)
        (alo, ahi), (blo, bhi) = sa["ci95"], sb["ci95"]
        assert not (alo <= bhi and blo <= ahi), "a 5x change must be detectable"


class TestGuardrails:
    def test_low_run_counts_warn(self, harness) -> None:
        src = _HARNESS.read_text(encoding="utf-8")
        assert "args.runs < 8" in src
        assert "WARNING" in src

    def test_failed_runs_are_dropped_not_averaged(self, harness) -> None:
        src = _HARNESS.read_text(encoding="utf-8")
        assert 'r.get("ok")' in src

    def test_log_limit_is_capped_below_the_cli_ceiling(self, harness) -> None:
        # `railway logs -n 9000` exits 1 with "Error in limit - Invalid input".
        assert harness._MAX_LOG_LINES <= 5000

    def test_a_failed_log_fetch_raises_instead_of_reporting_zero(self, harness) -> None:
        # The first version printed "turns matched=0" when the fetch had failed,
        # which is indistinguishable from a real measurement.
        src = _HARNESS.read_text(encoding="utf-8")
        idx = src.index("def _fetch_checkpoints")
        body = src[idx : src.index("def _stage_deltas")]
        assert "raise SystemExit" in body
        assert "proc.returncode != 0" in body

    def test_missing_server_checkpoints_warns(self, harness) -> None:
        src = _HARNESS.read_text(encoding="utf-8")
        assert "no server checkpoints matched" in src
