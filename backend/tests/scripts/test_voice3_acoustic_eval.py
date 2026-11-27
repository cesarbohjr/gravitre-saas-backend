import importlib.util
from pathlib import Path
import math
import struct
import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("acoustic", ROOT / "scripts/voice3_acoustic_eval.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def tone(freq=180, seconds=0.5, gain=0.35):
    return b"".join(struct.pack("<h", round(32767*gain*math.sin(2*math.pi*freq*i/m.RATE)))
                    for i in range(round(seconds*m.RATE)))


def test_clean_tone_pitch_and_integrity():
    result = m.analyze_pcm(tone())
    assert not m.integrity_failures(result)
    assert result["pitch_median_hz"] == pytest.approx(180, abs=5)


def test_silence_and_clipping_are_rejected():
    assert m.integrity_failures(m.analyze_pcm(bytes(m.RATE)))
    clipped = struct.pack("<h",32767)*(m.RATE//2)
    assert "out_of_bounds:clip_fraction" in m.integrity_failures(m.analyze_pcm(clipped))


def test_internal_pause_measured_separately_from_leading_silence():
    result = m.analyze_pcm(bytes(3200)+tone()+bytes(6400)+tone())
    assert result["max_internal_pause_ms"] == pytest.approx(200, abs=20)
    assert result["internal_pause_count"] == 1


def test_paired_pitch_shift_not_identity_claim():
    result = m.compare(m.analyze_pcm(tone(180)),m.analyze_pcm(tone(220)))
    assert result["pitch_delta_hz"] == pytest.approx(40, abs=8)
    assert result["identity_similarity"] == "NOT ESTABLISHED"


@pytest.mark.parametrize("data", [b"",b"x",bytes(10)])
def test_invalid_pcm_rejected(data):
    with pytest.raises(ValueError):
        m.analyze_pcm(data)


@pytest.mark.parametrize("invalid", [None,float("nan"),float("inf"),True])
def test_missing_or_invalid_metrics_fail_closed(invalid):
    result = m.analyze_pcm(tone())
    result["rms"] = invalid
    assert "missing_or_invalid:rms" in m.integrity_failures(result)


def test_word_error_rate_counts_missing_and_extra_words():
    assert m.word_error_rate("Please wait now","please wait") == pytest.approx(1/3)
    assert m.word_error_rate("Please wait","please wait wait") == 0.5
    assert m.word_error_rate("Please wait!","please wait") == 0


def test_gate_rejects_missing_skipped_and_failure():
    passed = dict.fromkeys(m.REQUIRED_GATES,"PASS")
    assert not m.certification_blockers(passed)
    for state in ("FAIL","NOT RUN","SKIPPED",True,None):
        assert m.certification_blockers({**passed,"v3_dialogue":state}) == ["v3_dialogue"]
    assert len(m.certification_blockers({})) == len(m.REQUIRED_GATES)
