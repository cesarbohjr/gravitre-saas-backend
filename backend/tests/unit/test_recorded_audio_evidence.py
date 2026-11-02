"""Offline tests of the recorded-audio integrity and paired-evidence gate."""
import hashlib
import wave

import pytest

from app.services.pipecat_voice.recorded_audio_evidence import (
    certify_recorded_trials, inspect_recording,
)


def _wav(tmp_path, name):
    path = tmp_path / name
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(bytes([1, 0]) * 1600)
    return path


def _row(engine, case_id, path):
    return {
        "engine": engine, "case_id": case_id,
        "first_audio_ms": 120, "interruption_ms": 80, "reconnect_ms": 200,
        "cancelled_write_executed": False, "output_wav": str(path),
        "recording_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def test_real_pcm_wav_is_inspected(tmp_path):
    p = _wav(tmp_path, "voice.wav")
    result = inspect_recording(str(p))
    assert result["sample_rate"] == 16000
    assert result["duration_s"] == pytest.approx(0.1)


def test_paired_recordings_cannot_self_certify(tmp_path):
    p = _wav(tmp_path, "voice.wav")
    result = certify_recorded_trials(
        [_row("pipecat", "case1", p), _row("livekit", "case1", p)],
        minimum_pairs=1,
    )
    assert result["recorded_evidence_sufficient"] is True
    assert result["certified"] is False
    assert result["adapter_selected"] is None
    assert result["quality_review"] == "NOT_RUN"


def test_unpaired_recordings_are_insufficient(tmp_path):
    p = _wav(tmp_path, "voice.wav")
    result = certify_recorded_trials([_row("pipecat", "case1", p)], minimum_pairs=1)
    assert result["recorded_evidence_sufficient"] is False


def test_mismatched_recording_hash_fails(tmp_path):
    p = _wav(tmp_path, "voice.wav")
    row = _row("pipecat", "case1", p)
    row["recording_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="integrity"):
        certify_recorded_trials([row], minimum_pairs=1)


def test_cancelled_write_is_not_safe(tmp_path):
    p = _wav(tmp_path, "voice.wav")
    rows = [_row("pipecat", "case1", p), _row("livekit", "case1", p)]
    rows[0]["cancelled_write_executed"] = True
    result = certify_recorded_trials(rows, minimum_pairs=1)
    assert result["cancelled_write_safety_passed"] is False
    assert result["certified"] is False
