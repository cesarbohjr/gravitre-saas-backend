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


def test_favorable_aggregates_cannot_substitute_for_real_audio_and_quality_evidence():
    result = compare_engines([trial("duplex") for _ in range(20)]
                             + [trial("pipecat", latency=90) for _ in range(20)]
                             + [trial("livekit", latency=95) for _ in range(20)])
    assert result["sample_counts_sufficient"]
    assert result["metrics_only_improvement"] == {"pipecat": True, "livekit": True}
    assert not result["evidence_sufficient"]
    assert not result["recommend_pipecat"] and not result["recommend_livekit"]
    assert result["default_engine"] == "duplex"


def test_cancelled_write_violation_blocks_adoption():
    rows = [trial("duplex") for _ in range(20)]
    rows += [trial("pipecat", latency=90, unsafe=i == 0) for i in range(20)]
    assert not compare_engines(rows)["recommend_pipecat"]


def test_worse_completion_blocks_adoption():
    rows = [trial("duplex") for _ in range(20)]
    rows += [trial("pipecat", latency=90, completed=i != 0) for i in range(20)]
    assert not compare_engines(rows)["recommend_pipecat"]


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "1"])
def test_invalid_metrics_rejected(value):
    with pytest.raises(ValueError):
        trial("pipecat", latency=value)


@pytest.mark.parametrize('value', ['false', 0, 1, None])
def test_nonboolean_outcome_flags_rejected(value):
    with pytest.raises(ValueError):
        trial('pipecat', completed=value)
    with pytest.raises(ValueError):
        trial('pipecat', unsafe=value)


@pytest.mark.parametrize('value', [True, 0, -1, 1.5, '20'])
def test_invalid_sample_threshold_cannot_relax_gate(value):
    with pytest.raises(ValueError):
        compare_engines([], minimum_per_engine=value)


def test_missing_livekit_and_equal_metrics_cannot_imply_a_selection():
    rows = [trial(engine) for engine in ('duplex', 'pipecat') for _ in range(20)]
    assert not compare_engines(rows)['sample_counts_sufficient']
    rows += [trial('livekit') for _ in range(20)]
    result = compare_engines(rows)
    assert result['sample_counts_sufficient']
    assert result['metrics_only_improvement'] == {'pipecat': False, 'livekit': False}
    assert result['selection_status'] == 'BLOCKED_RAW_AGGREGATES_NOT_LIVE_EVIDENCE'
