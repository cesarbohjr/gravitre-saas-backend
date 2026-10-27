"""Regression coverage for the Phase 2 Pipecat evaluation gate."""
import pytest

from app.services.pipecat_voice.engine_benchmark import VoiceTrial, compare_engines


def trial(engine, *, latency=100, gap=20, interruption=50, cost=.01,
          completed=True, unsafe=False):
    return VoiceTrial(engine, latency, gap, interruption, completed, cost, unsafe)


def test_insufficient_evidence_never_switches_default():
    result = compare_engines([trial("pipecat", latency=1)])
    assert result["recommend_pipecat"] is False
    assert result["default_engine"] == "duplex"


def test_comparable_safe_trials_can_recommend_pipecat():
    result = compare_engines([trial("duplex") for _ in range(20)]
                             + [trial("pipecat", latency=90) for _ in range(20)])
    assert result["evidence_sufficient"]
    assert result["recommend_pipecat"]
    assert result["default_engine"] == "duplex"


def test_cancelled_write_violation_blocks_adoption():
    rows = [trial("duplex") for _ in range(20)]
    rows += [trial("pipecat", latency=90, unsafe=i == 0) for i in range(20)]
    assert not compare_engines(rows)["recommend_pipecat"]


def test_worse_completion_blocks_adoption():
    rows = [trial("duplex") for _ in range(20)]
    rows += [trial("pipecat", latency=90, completed=i != 0) for i in range(20)]
    assert not compare_engines(rows)["recommend_pipecat"]


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_metrics_rejected(value):
    with pytest.raises(ValueError):
        trial("pipecat", latency=value)
