"""Privacy-safe, per-socket Flux boundary and outbound PCM evidence.

This is observation, not a second source of turn authority. A provider final can
be wrong even when it is marked final; a new start soon after such a final is a
*suspect*, not proof of an STT error. No transcript, tenant, identity, raw PCM,
or credentials are captured. Audio is observed immediately before the websocket
output processor; client playback still needs independent browser receipts.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from pipecat.frames.frames import Frame, TTSAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class VoiceTurnAudioEvidence:
    def __init__(self, *, clock: Callable[[], float] = time.perf_counter,
                 resume_window_s: float = 1.5) -> None:
        self._clock = clock
        self._resume_window_s = resume_window_s
        self.epoch = 0
        self.eager_candidates = 0
        self.eager_cancelled = 0
        self.provider_finals = 0
        self.committed_stops = 0
        self.duplicate_finals = 0
        self.duplicate_stops = 0
        self.suspected_false_finals = 0
        self.suspected_false_finals_with_audio = 0
        self.outbound_audio_frames = 0
        self._audio_since_stop = 0
        self.audio_without_committed_stop = 0
        self.first_audio_after_stop_ms: float | None = None
        self._last_final_at: float | None = None
        self._last_stop_at: float | None = None
        self._first_audio_epoch: int | None = None

    def new_start(self) -> None:
        now = self._clock()
        if (self._last_final_at is not None and self._last_stop_at is not None
                and 0 <= now - self._last_final_at <= self._resume_window_s):
            # Ambiguous: this also includes genuinely rapid independent turns.
            self.suspected_false_finals += 1
            if self._audio_since_stop:
                self.suspected_false_finals_with_audio += 1
        self.epoch += 1
        self._last_final_at = None
        self._last_stop_at = None
        self._first_audio_epoch = None
        self._audio_since_stop = 0
        self.first_audio_after_stop_ms = None

    def eager(self) -> None:
        self.eager_candidates += 1

    def eager_cancel(self) -> None:
        self.eager_cancelled += 1

    def final(self) -> None:
        self.provider_finals += 1
        self._last_final_at = self._clock()

    def duplicate_final(self) -> None:
        self.duplicate_finals += 1

    def stop(self) -> None:
        self.committed_stops += 1
        self._last_stop_at = self._clock()
        self._audio_since_stop = 0

    def duplicate_stop(self) -> None:
        self.duplicate_stops += 1

    def audio(self) -> None:
        self.outbound_audio_frames += 1
        if self._last_stop_at is None:
            self.audio_without_committed_stop += 1
            return
        self._audio_since_stop += 1
        if self._first_audio_epoch != self.epoch:
            self._first_audio_epoch = self.epoch
            self.first_audio_after_stop_ms = round(
                max(0.0, self._clock() - self._last_stop_at) * 1000.0, 2
            )

    def snapshot(self) -> dict[str, int | float | None]:
        return {
            "epoch": self.epoch,
            "eager_candidates": self.eager_candidates,
            "eager_cancelled": self.eager_cancelled,
            "provider_finals": self.provider_finals,
            "committed_stops": self.committed_stops,
            "duplicate_finals": self.duplicate_finals,
            "duplicate_stops": self.duplicate_stops,
            "suspected_false_finals": self.suspected_false_finals,
            "suspected_false_finals_with_audio": self.suspected_false_finals_with_audio,
            "outbound_audio_frames": self.outbound_audio_frames,
            "audio_without_committed_stop": self.audio_without_committed_stop,
            "first_audio_after_stop_ms": self.first_audio_after_stop_ms,
        }


class OutboundAudioEvidenceProcessor(FrameProcessor):
    """Observe actual PCM frames handed toward the websocket output stage."""

    def __init__(self, *, evidence: VoiceTurnAudioEvidence,
                 turn_trace: Any | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._evidence = evidence
        self._turn_trace = turn_trace

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM and isinstance(frame, TTSAudioRawFrame):
            self._evidence.audio()
            if self._turn_trace is not None:
                self._turn_trace.add_extra("voice_boundary_audio", self._evidence.snapshot())
        await self.push_frame(frame, direction)
