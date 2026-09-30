"""Standing contract for natural realtime TTS delivery."""
from __future__ import annotations

from pathlib import Path

from app.services.pipecat_voice.pipeline import LIVE_VOICE_OUTPUT_SAMPLE_RATE
from app.services.tier1_voice_service import CONVERSATIONAL_VOICE_SETTINGS
from app.services.voice_session_service import split_speakable_chunks


ROOT = Path(__file__).resolve().parents[4]
PIPELINE = (ROOT / "backend/app/services/pipecat_voice/pipeline.py").read_text(encoding="utf-8")


def test_partial_streaming_phrase_is_not_synthesized_as_a_sentence() -> None:
    ready, remainder = split_speakable_chunks("I can help you with", min_chars=12)
    assert ready == []
    assert remainder == "I can help you with"


def test_full_sentence_is_released_immediately() -> None:
    ready, remainder = split_speakable_chunks("I can help you with that.", min_chars=12)
    assert ready == ["I can help you with that."]
    assert remainder == ""


def test_elevenlabs_auto_mode_only_receives_sentence_level_chunks_by_contract() -> None:
    assert "auto_mode=True" in PIPELINE
    assert "preserves partial phrases until sentence" in PIPELINE


def test_stt_input_stays_16k_while_tts_output_is_24k() -> None:
    assert LIVE_VOICE_OUTPUT_SAMPLE_RATE == 24000
    assert "audio_in_sample_rate=16000" in PIPELINE
    assert "audio_out_sample_rate=LIVE_VOICE_OUTPUT_SAMPLE_RATE" in PIPELINE
    assert "sample_rate=LIVE_VOICE_OUTPUT_SAMPLE_RATE" in PIPELINE


def test_voice_settings_avoid_style_exaggeration() -> None:
    assert CONVERSATIONAL_VOICE_SETTINGS["stability"] == 0.5
    assert CONVERSATIONAL_VOICE_SETTINGS["similarity_boost"] == 0.75
    assert CONVERSATIONAL_VOICE_SETTINGS["style"] == 0.0
