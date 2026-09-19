"""TTS context cancel must close synthesis without dropping the session WS."""
from __future__ import annotations

import pytest

from app.services.pipecat_voice.tts_context_cancel import cancel_elevenlabs_tts_context


class _FakeElevenLabs:
    def __init__(self) -> None:
        self._websocket = object()
        self._turn_context_id = "ctx-live"
        self.closed: list[str] = []
        self.disconnected = False

    def get_active_audio_context_id(self) -> str:
        return "ctx-live"

    async def _close_context(self, context_id: str) -> None:
        self.closed.append(context_id)

    async def _disconnect(self) -> None:
        self.disconnected = True
        self._websocket = None


@pytest.mark.asyncio
async def test_cancel_closes_context_and_keeps_websocket():
    tts = _FakeElevenLabs()
    ws = tts._websocket
    result = await cancel_elevenlabs_tts_context(tts, keep_session=True)
    assert result["cancelled"] is True
    assert result["method"] == "elevenlabs_close_context"
    assert result["session_kept"] is True
    assert tts.closed == ["ctx-live"]
    assert tts.disconnected is False
    assert tts._websocket is ws


@pytest.mark.asyncio
async def test_cancel_noop_when_no_active_context():
    class Empty:
        _websocket = object()

        def get_active_audio_context_id(self):
            return None

    result = await cancel_elevenlabs_tts_context(Empty(), keep_session=True)
    assert result["cancelled"] is False
    assert result["session_kept"] is True
