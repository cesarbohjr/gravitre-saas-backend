"""Voice V2 commit barrier between speculative prefetch and the user aggregator.

Deepgram Flux may emit an EagerTranscriptionFrame with a provisional
ProposedUserStoppedSpeakingFrame before its authoritative final transcript.
The eager transcript can warm a scoped, read-only speculative computation, but
must never reach the user aggregator: it can otherwise start an assistant
response while the user is still talking.

Preserve normal frame order, except a provisional stop is held until the final
TranscriptionFrame. A resumed turn invalidates that pending stop. The original
final transcript and its stop proposal remain owned by Pipecat's turn strategy.
No provider call, tool action, approval or durable history mutation occurs here.
"""
from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from pipecat.frames.frames import (
    EagerEndOfTurnCancelFrame,
    EagerTranscriptionFrame,
    Frame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class CommittedTurnBarrierProcessor(FrameProcessor):
    """Never promote probable-EOT into an aggregator-owned committed user turn."""

    def __init__(self, *, clock: Callable[[], float] = time.perf_counter, **kwargs):
        super().__init__(**kwargs)
        self._hold_clock = clock
        self._pending_stop: Frame | None = None
        self._pending_stop_at: float | None = None
        self._last_stop_hold_ms: float | None = None
        self._final_seen = False
        self._stop_forwarded = False
        # Exact provider retransmission is not a second user turn. The
        # timestamp key avoids suppressing two legitimate identical replies.
        self._recent_final_keys: deque[tuple[str, str, str]] = deque(maxlen=32)
        self._suppressed_eager = 0

    @property
    def suppressed_eager_count(self) -> int:
        return self._suppressed_eager

    @property
    def last_stop_hold_ms(self) -> float | None:
        """Measured hold of the last released stop; never contains user text."""
        return self._last_stop_hold_ms

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, EagerTranscriptionFrame):
            self._final_seen = False
            self._suppressed_eager += 1
            return

        if isinstance(frame, EagerEndOfTurnCancelFrame):
            # The speaker continued. Never replay a provisional stop.
            self._pending_stop = None
            self._pending_stop_at = None
            self._final_seen = False
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, ProposedUserStartedSpeakingFrame):
            # A fresh utterance invalidates a stop from a previous candidate.
            self._pending_stop = None
            self._pending_stop_at = None
            self._final_seen = False
            self._stop_forwarded = False
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, ProposedUserStoppedSpeakingFrame):
            if self._stop_forwarded:
                # A duplicate native stop must never trigger a second answer.
                return
            if not self._final_seen:
                # Retain the earliest proposal time if Flux retries its stop.
                if self._pending_stop_at is None:
                    self._pending_stop_at = self._hold_clock()
                self._pending_stop = frame
                return
            self._stop_forwarded = True
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame):
            # A retransmitted provider final must not enter the LLM context
            # twice. Identical text at a NEW timestamp remains a new utterance.
            timestamp = str(getattr(frame, "timestamp", "") or "")
            if timestamp:
                key = (
                    str(getattr(frame, "user_id", "") or ""),
                    timestamp,
                    str(getattr(frame, "text", "") or ""),
                )
                if key in self._recent_final_keys:
                    return
                self._recent_final_keys.append(key)
            # Pipecat must receive authoritative words before resolving stop.
            await self.push_frame(frame, direction)
            if self._pending_stop is not None:
                pending = self._pending_stop
                self._pending_stop = None
                if self._pending_stop_at is not None:
                    self._last_stop_hold_ms = max(
                        0.0, (self._hold_clock() - self._pending_stop_at) * 1000.0
                    )
                self._pending_stop_at = None
                await self.push_frame(pending, direction)
                self._stop_forwarded = True
            self._final_seen = True
            return

        await self.push_frame(frame, direction)
