"""Voice Gateway service unit tests."""
from __future__ import annotations

from app.config import Settings
from app.services.tier1_voice_service import deepgram_live_ws_url
from app.services.voice_gateway_service import build_connect_twiml


def test_build_connect_twiml_includes_stream() -> None:
    settings = Settings()
    twiml = build_connect_twiml(settings, "sess-123", disclosure="Recorded.")
    assert "<Stream" in twiml
    assert "sess-123" in twiml
    assert "Recorded." in twiml


def test_deepgram_pstn_url_uses_mulaw_8k() -> None:
    settings = Settings()
    url = deepgram_live_ws_url(settings, pstn=True)
    assert "encoding=mulaw" in url
    assert "sample_rate=8000" in url
    assert "encoding=linear16" not in url
