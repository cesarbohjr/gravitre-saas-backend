"""Bounded PCM observation on the existing live voice pipeline."""
from __future__ import annotations

from io import BytesIO
import asyncio
import wave
from typing import Any

from pipecat.frames.frames import InputAudioRawFrame, TranscriptionFrame, EndFrame, CancelFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


class AcousticTapProcessor(FrameProcessor):
    """Observe a maximum of eight seconds; never retain raw audio after a turn.

    STT passes PCM downstream. Only supported mono s16le frames are accepted;
    WAV wrapping preserves their actual rate for the existing feature extractor.
    """

    def __init__(self, *, settings: Any, org_id: str, user_id: str,
                 conversation_id_getter: Any, agent_id: str | None = None,
                 audio_origin_getter: Any = lambda: "user_mic", **kwargs: Any):
        super().__init__(**kwargs)
        self._settings = settings
        self._org_id = org_id
        self._user_id = user_id
        self._conversation_id_getter = conversation_id_getter
        self._agent_id = agent_id
        self._audio_origin_getter = audio_origin_getter
        self._pcm = bytearray()
        self._rate: int | None = None
        self._analysis_task: Any = None

    def _observe(self, frame: InputAudioRawFrame) -> None:
        if self._audio_origin_getter() != "user_mic":
            self._pcm.clear()
            self._rate = None
            return
        rate = frame.sample_rate
        if frame.num_channels != 1 or rate not in {8000, 16000, 24000, 48000}:
            self._pcm.clear()
            self._rate = None
            return
        if self._rate != rate:
            self._pcm.clear()
            self._rate = rate
        limit = rate * 2 * 8
        self._pcm.extend(frame.audio[-limit:])
        if len(self._pcm) > limit:
            del self._pcm[:-limit]  # Keep speech after idle time, not old silence.

    def _flush(self) -> None:
        pcm = bytes(self._pcm)
        rate = self._rate
        self._pcm.clear()
        self._rate = None
        if not pcm or not rate:
            return
        if self._analysis_task is not None and not self._analysis_task.done():
            return  # At most one analysis per session, regardless of STT rate.
        from app.services.voice_acoustic_signal import schedule_acoustic_analysis
        from app.workflows.repository import get_supabase_client
        from app.core.logging import get_logger
        try:
            output = BytesIO()
            with wave.open(output, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(rate)
                wav.writeframes(pcm[:len(pcm) - len(pcm) % 2])
            self._analysis_task = schedule_acoustic_analysis(
                client=get_supabase_client(self._settings), org_id=self._org_id,
                user_id=self._user_id,
                conversation_id=self._conversation_id_getter(),
                agent_id=self._agent_id, audio_bytes=output.getvalue(),
            )
        except Exception:
            get_logger(__name__).warning("live_acoustic_observation_skipped", exc_info=True)

    async def process_frame(self, frame: Any, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM:
            if isinstance(frame, InputAudioRawFrame):
                self._observe(frame)
            elif isinstance(frame, TranscriptionFrame):
                self._flush()
            elif isinstance(frame, (EndFrame, CancelFrame)):
                self._pcm.clear()
                self._rate = None
        await self.push_frame(frame, direction)

    async def cleanup(self) -> None:
        self._pcm.clear()
        self._rate = None
        if self._analysis_task is not None and not self._analysis_task.done():
            self._analysis_task.cancel()
            await asyncio.gather(self._analysis_task, return_exceptions=True)
        await super().cleanup()
