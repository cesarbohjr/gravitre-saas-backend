"""Bounded, opt-in Flux hard-final stability window.

After the existing committed-turn barrier, hold the *actual* final transcript
and stop until a short quiet interval expires. A subsequent start during that
interval keeps the original words in the SAME canonical user turn. If the user
continues with "wait" after "yes", the approval engine sees both clauses and
never receives an isolated confirmation.

Only the turn aggregator is delayed: interruption/control frames still flow
immediately, and speculative computation remains upstream. This is a heuristic,
not proof of speaker intent; a genuinely separate fast second turn can be
combined. Disabled by default until paired scenario/acoustic certification.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InterruptionFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# Short confirmations are consequential in ACT WITH APPROVAL. Never let an
# isolated "yes" authorize a connector write while the user may still add
# "wait", "but", "not yet", or a correction.
_CONFIRMATIONS = frozenset({
    "yes", "yeah", "yep", "sure", "approve", "approved", "confirm",
    "confirmed", "go ahead", "send it", "do it", "okay", "ok",
})


def is_short_confirmation(text: str) -> bool:
    normalized = " ".join((text or "").lower().strip(" .!?," ).split())
    return normalized in _CONFIRMATIONS


class FinalTurnStabilityProcessor(FrameProcessor):
    """One bounded grace interval per stop; never launch a second runtime."""

    def __init__(
        self, *,
        normal_window_ms: int = 400,
        approval_window_ms: int = 1200,
        voice_session: Any | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.normal_window_ms = max(0, min(1500, int(normal_window_ms)))
        self.approval_window_ms = max(
            self.normal_window_ms, min(1500, int(approval_window_ms))
        )
        self._session = voice_session
        self._sleeper = sleeper
        self._lock = asyncio.Lock()
        self._finals: list[TranscriptionFrame] = []
        self._stops: list[Frame] = []
        self._release_task: asyncio.Task | None = None
        self._generation = 0
        self._continuing = False
        self.rejoined_segments = 0
        self.released_turns = 0
        self.cancelled_turns = 0

    def _cancel_release(self) -> None:
        self._generation += 1
        task, self._release_task = self._release_task, None
        if task is not None and not task.done():
            task.cancel()

    def _clear(self) -> None:
        self._cancel_release()
        self._finals.clear()
        self._stops.clear()
        self._continuing = False

    def _delay(self) -> float:
        approval_expected = getattr(self._session, "pending_approval", None) is not None
        confirm = any(is_short_confirmation(str(f.text or "")) for f in self._finals)
        ms = self.approval_window_ms if approval_expected or confirm else self.normal_window_ms
        return ms / 1000.0

    async def _release_after(self, generation: int, delay: float) -> None:
        try:
            await self._sleeper(delay)
            async with self._lock:
                if generation != self._generation or not self._finals or not self._stops:
                    return
                finals, stops = self._finals[:], self._stops[:]
                self._finals.clear()
                self._stops.clear()
                self._release_task = None
                self._continuing = False
                # Preserve the real provider frames, their order, and the
                # canonical Pipecat stop; no invented transcript or approval.
                for frame in (*finals, *stops):
                    await self.push_frame(frame, FrameDirection.DOWNSTREAM)
                self.released_turns += 1
        except asyncio.CancelledError:
            return

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return
        async with self._lock:
            if isinstance(frame, (CancelFrame, EndFrame)):
                self._clear()
                await self.push_frame(frame, direction)
                return
            if isinstance(frame, InterruptionFrame):
                # Explicit interruption must never wait for the quiet window.
                await self.push_frame(frame, direction)
                return
            if isinstance(frame, (ProposedUserStartedSpeakingFrame, UserStartedSpeakingFrame)):
                if self._finals:
                    # A new start inside the window means the previous final
                    # was not yet a safe authorization/answer boundary.
                    if not self._continuing:
                        self.rejoined_segments += 1
                    self._continuing = True
                    self._cancel_release()
                    self._stops.clear()
                    return
                await self.push_frame(frame, direction)
                return
            if isinstance(frame, TranscriptionFrame):
                if str(getattr(frame, "user_id", "") or "") == "browser":
                    # Explicit typed ingress has its own synthetic bookends.
                    await self.push_frame(frame, direction)
                    return
                self._cancel_release()
                self._finals.append(frame)
                return
            if isinstance(frame, (ProposedUserStoppedSpeakingFrame, UserStoppedSpeakingFrame)):
                if not self._finals:
                    # An upstream filler-only final was filtered. Pass the
                    # empty-turn cleanup stop through without synthesizing text.
                    await self.push_frame(frame, direction)
                    return
                self._stops.append(frame)
                self._cancel_release()
                generation = self._generation
                self._release_task = self.create_task(
                    self._release_after(generation, self._delay())
                )
                return
            await self.push_frame(frame, direction)
