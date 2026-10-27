"""Acceptance analyzer tests use generated fixtures, never claim live evidence."""
import importlib.util
import json
import math
import struct
import wave
from pathlib import Path


def _module():
    path = Path(__file__).resolve().parents[3] / "scripts" / "measure-voice-audio-acceptance.py"
    spec = importlib.util.spec_from_file_location("voice_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wav(path: Path):
    rate = 16000
    samples = []
    for active, duration in ((True, .2), (False, .12), (True, .2)):
        for i in range(int(rate * duration)):
            samples.append(int(12000 * math.sin(2 * math.pi * 440 * i / rate)) if active else 0)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(struct.pack("<" + "h" * len(samples), *samples))


def test_detects_internal_recorded_gap(tmp_path):
    path = tmp_path / "voice.wav"
    _wav(path)
    result = _module().analyze_wav(path)
    assert result["gap_count"] >= 1
    assert result["longest_internal_gap_ms"] >= 100


def test_compares_profiles_and_interruption_timestamps(tmp_path):
    _wav(tmp_path / "voice.wav")
    result = _module().analyze_manifest({
        "recordings": [
            {"profile": profile, "wav": "voice.wav",
             "tts_request_ms": 100, "first_audio_ms": 250,
             "interruption_requested_ms": 1000, "audio_stopped_ms": 1065}
            for profile in ("light", "medium", "deep")
        ]
    }, tmp_path)
    assert set(result["profiles"]) == {"light", "medium", "deep"}
    assert result["profiles"]["light"]["median_tts_first_audio_ms"] == 150
    assert result["profiles"]["medium"]["median_interruption_stop_ms"] == 65


def test_rejects_path_escape(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="escapes"):
        _module().analyze_manifest({"recordings": [{"profile": "light", "wav": "../elsewhere.wav"}]}, tmp_path)
