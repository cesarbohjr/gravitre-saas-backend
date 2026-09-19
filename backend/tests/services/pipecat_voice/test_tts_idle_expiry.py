"""TTS idle-expiry policy (warmth without dropping mid-speech)."""
from __future__ import annotations

from app.services.pipecat_voice.tts_warmup import tts_idle_should_refresh


def test_idle_refresh_only_after_expiry_and_not_while_speaking():
    assert tts_idle_should_refresh(
        last_activity_monotonic=0.0, now_monotonic=10.0, idle_expiry_s=45
    ) is False
    assert tts_idle_should_refresh(
        last_activity_monotonic=0.0, now_monotonic=46.0, idle_expiry_s=45
    ) is True
    assert tts_idle_should_refresh(
        last_activity_monotonic=0.0,
        now_monotonic=90.0,
        idle_expiry_s=45,
        speaking=True,
    ) is False
    assert tts_idle_should_refresh(
        last_activity_monotonic=None, now_monotonic=100.0
    ) is False
