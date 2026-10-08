"""Server-side audio framing for browser playback.

The browser decodes every ``audio`` message as little-endian PCM16. A message
with an odd byte count would split a sample across two messages, so these pin
what reaches the serializer: whatever byte lengths the TTS emits, the output
transport re-chunks to whole, even-sized chunks at LIVE_VOICE_OUTPUT_SAMPLE_RATE,
and the serializer passes those bytes through unchanged.
"""
from __future__ import annotations

import asyncio
import base64
import json
from unittest.mock import MagicMock

import pytest

pytest.importorskip("pipecat")

from pipecat.frames.frames import TTSAudioRawFrame  # noqa: E402
from pipecat.transports.base_output import BaseOutputTransport  # noqa: E402
from pipecat.transports.base_transport import TransportParams  # noqa: E402

from app.services.pipecat_voice.json_audio_serializer import GravitreJsonAudioSerializer  # noqa: E402
from app.services.pipecat_voice.pipeline import LIVE_VOICE_OUTPUT_SAMPLE_RATE  # noqa: E402


class _ListQueue:
    def __init__(self) -> None:
        self.items: list = []

    async def put(self, item) -> None:
        self.items.append(item)


def _sender(rate: int):
    params = TransportParams(audio_out_enabled=True, audio_out_sample_rate=rate)
    chunk = int(rate / 100) * 2 * params.audio_out_10ms_chunks
    sender = BaseOutputTransport.MediaSender(
        MagicMock(), destination=None, sample_rate=rate, audio_chunk_size=chunk, params=params
    )
    sender._audio_queue = _ListQueue()
    return sender, chunk


def test_odd_tts_chunks_leave_the_transport_as_even_whole_samples():
    rate = LIVE_VOICE_OUTPUT_SAMPLE_RATE
    sender, chunk = _sender(rate)
    assert chunk % 2 == 0
    pcm = bytes((i * 37) % 256 for i in range(2 * 4001))
    # ElevenLabs-style uneven pieces, several of them odd-length.
    cuts = [0, 1, 1002, 1003, 2921, 5000, 7777, len(pcm)]

    async def run():
        for a, b in zip(cuts, cuts[1:]):
            await sender.handle_audio_frame(TTSAudioRawFrame(pcm[a:b], rate, 1))
        await sender._enqueue_flushed_audio_buffer()

    asyncio.run(run())
    frames = sender._audio_queue.items
    assert frames, "transport queued no audio"
    assert all(len(f.audio) == chunk for f in frames)
    assert all(f.sample_rate == rate for f in frames)
    sent = b"".join(f.audio for f in frames)
    # Same bytes in the same order; only silence padding on the last chunk.
    assert sent[: len(pcm)] == pcm
    assert set(sent[len(pcm):]) <= {0}


def test_serializer_passes_pcm_bytes_and_rate_through_unchanged():
    ser = GravitreJsonAudioSerializer()
    audio = bytes(range(256)) * 15  # 3840 bytes = 80 ms at 24 kHz

    async def run():
        return await ser.serialize(TTSAudioRawFrame(audio, LIVE_VOICE_OUTPUT_SAMPLE_RATE, 1))

    msg = json.loads(asyncio.run(run()))
    assert msg["type"] == "audio"
    assert msg["sample_rate"] == LIVE_VOICE_OUTPUT_SAMPLE_RATE == 24000
    assert msg["num_channels"] == 1
    assert base64.b64decode(msg["pcm16_b64"]) == audio
