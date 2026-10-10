"""Answer-first scheduling of filler and progress speech (voice_answer_first_v1).

Without it, the LLM bridge hands every acknowledgement ("Okay, give me a
sec.") and tool line ("Let me check your CRM.", "I found 3 of them.") to the
TTS the moment it is decided. The TTS turns text into audio faster than real
time, so those lines pile up as audio queued in the output transport, and the
answer, when it arrives, plays only after all of them. Measured on the voice
bench: the answer was ready about 2.5 s before it was heard.

With the flag on, non-answer lines are held as text and released one at a
time, only when the audio already queued is about to run out:

* the line ahead finishes at its own sentence end (lines are one sentence;
  nothing already handed to the TTS is cut);
* when answer text is ready, every line not yet released is dropped, so the
  answer is queued behind at most the line already playing;
* a progress line is released only if it still describes work that is
  running when it would play ("Let me check X" after X finished is dropped);
* filler is never released once the answer is available (it is dropped with
  the rest);
* a tool's result line ("I found 3 of them.") waits ``RESULT_LINE_GRACE_S``
  first, since the answer usually follows a finished tool within a second;
* a line identical to one already said this turn is not said again.

Labels stay honest: a held line is shown to the client and recorded for
history (assistant_text) only when it is released, so the transcript and the
heard-text accounting contain only what was actually spoken. The answer text,
and every check on it, is untouched: this only decides whether and when the
non-answer lines are spoken.

``PlayoutClock`` estimates the audio queued ahead of the speaker from the
audio frames that reach the output transport (which plays them in real time).
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from pipecat.frames.frames import Frame, InterruptionFrame, OutputAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.core.logging import get_logger

logger = get_logger(__name__)

# Release the next line when this much queued audio is left: about one TTS
# first-byte time, so the line's audio arrives as the previous one ends.
RELEASE_LEAD_S = 0.35
POLL_S = 0.05
# A released line that produced no audio within this long no longer holds
# the next one back.
RELEASE_AUDIO_WAIT_S = 1.5
# A released line counts as synthesized once its audio stopped arriving for
# this long (the TTS produces faster than real time, in bursts).
AUDIO_QUIET_S = 0.25
# A tool's result line ("I found 3 of them.") waits this long before it may
# play: the answer usually follows a finished tool within about a second, and
# then the line is dropped instead of being spoken ahead of it.
RESULT_LINE_GRACE_S = 1.0


class PlayoutClock:
    """Seconds of audio queued ahead of the speaker, from frames sent to the transport."""

    def __init__(self, clock: Callable[[], float] = lambda: time.monotonic()) -> None:
        self._clock = clock
        self._horizon = 0.0
        self.audio_frames = 0
        self.last_audio_at: float | None = None

    def note_audio(self, seconds: float) -> None:
        if seconds <= 0:
            return
        now = self._clock()
        self._horizon = max(self._horizon, now) + seconds
        self.audio_frames += 1
        self.last_audio_at = now

    def quiet_for(self) -> float:
        """Seconds since the last audio frame (infinite before the first)."""
        if self.last_audio_at is None:
            return float("inf")
        return max(0.0, self._clock() - self.last_audio_at)

    def note_audio_frame(self, frame: Any) -> None:
        audio = getattr(frame, "audio", None) or b""
        rate = int(getattr(frame, "sample_rate", 0) or 0)
        channels = max(1, int(getattr(frame, "num_channels", 1) or 1))
        if rate > 0 and audio:
            self.note_audio(len(audio) / (2 * channels) / rate)

    def remaining(self) -> float:
        return max(0.0, self._horizon - self._clock())

    def reset(self) -> None:
        """A barge-in flushed the transport's queue."""
        self._horizon = self._clock()


class PlayoutClockProcessor(FrameProcessor):
    """Feeds a ``PlayoutClock`` from the audio heading to the output transport."""

    def __init__(self, clock: PlayoutClock, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._playout = clock

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM:
            if isinstance(frame, InterruptionFrame):
                self._playout.reset()
            elif isinstance(frame, OutputAudioRawFrame):
                self._playout.note_audio_frame(frame)
        await self.push_frame(frame, direction)


@dataclass
class _Line:
    text: str
    kind: str
    still_relevant: Callable[[], bool] | None
    queued_at: float
    not_before: float = 0.0


SpeakLine = Callable[[str, str], Awaitable[None]]


@dataclass
class AnswerFirstStats:
    queued: int = 0
    released: int = 0
    dropped_for_answer: int = 0
    dropped_stale: int = 0
    dropped_repeat: int = 0
    released_by_kind: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "queued": self.queued,
            "released": self.released,
            "dropped_for_answer": self.dropped_for_answer,
            "dropped_stale": self.dropped_stale,
            "dropped_repeat": self.dropped_repeat,
            "released_by_kind": dict(self.released_by_kind),
        }


class AnswerFirstSpeech:
    """One turn's held filler / progress lines, released just in time or dropped."""

    def __init__(
        self,
        *,
        speak: SpeakLine,
        playout: PlayoutClock | None,
        lead_s: float = RELEASE_LEAD_S,
        poll_s: float = POLL_S,
        clock: Callable[[], float] = lambda: time.monotonic(),
    ) -> None:
        self._speak = speak
        self._playout = playout
        self._lead_s = lead_s
        self._poll_s = poll_s
        self._clock = clock
        self._pending: list[_Line] = []
        self._answer_ready = False
        # After a release: wait for its audio before releasing the next line.
        self._awaiting_audio_since: float | None = None
        self._frames_at_release = 0
        self._wake = asyncio.Event()
        self._released_texts: set[str] = set()
        self.stats = AnswerFirstStats()

    @property
    def answer_ready(self) -> bool:
        return self._answer_ready

    def has_pending(self) -> bool:
        return bool(self._pending)

    def enqueue(
        self,
        text: str,
        kind: str,
        still_relevant: Callable[[], bool] | None = None,
        *,
        hold_s: float = 0.0,
    ) -> bool:
        """Hold a non-answer line. False when it was dropped instead.

        Once answer text has been spoken, only a line that describes work still
        running (it has a ``still_relevant`` probe, e.g. a tool started after
        the answer's first sentence) is held; it plays after the answer audio
        queued ahead of it, if the work is still running then. Filler and
        result lines are dropped.
        """
        if self._answer_ready and still_relevant is None:
            self.stats.dropped_for_answer += 1
            return False
        now = self._clock()
        self._pending.append(_Line(text, kind, still_relevant, now, now + max(0.0, hold_s)))
        self.stats.queued += 1
        self._wake.set()
        return True

    def mark_answer_ready(self) -> int:
        """Answer text is about to be spoken: drop every line not yet released."""
        self._answer_ready = True
        dropped = len(self._pending)
        if dropped:
            logger.info("pipecat_voice_answer_first_dropped count=%s kinds=%s", dropped, [p.kind for p in self._pending])
        self.stats.dropped_for_answer += dropped
        self._pending.clear()
        self._wake.set()
        return dropped

    def _audio_settled(self) -> bool:
        if self._awaiting_audio_since is None:
            return True
        if self._playout is None:
            return True
        if self._playout.audio_frames > self._frames_at_release:
            # Its audio started; wait until all of it has come out of the TTS,
            # so "queued audio" includes the whole line.
            return self._playout.quiet_for() >= AUDIO_QUIET_S
        return self._clock() - self._awaiting_audio_since >= RELEASE_AUDIO_WAIT_S

    def _due(self) -> bool:
        if not self._pending:
            return False
        if self._pending[0].not_before > self._clock():
            return False
        if not self._audio_settled():
            return False
        remaining = self._playout.remaining() if self._playout is not None else 0.0
        return remaining <= self._lead_s

    def _keep(self, line: _Line) -> bool:
        """Whether a line is still worth saying now (else it is counted as dropped)."""
        key = " ".join(line.text.split()).casefold()
        if key in self._released_texts:
            # The same line was already said this turn ("I found 3 of them."
            # after a second tool): it adds nothing.
            self.stats.dropped_repeat += 1
            return False
        relevant = True
        if line.still_relevant is not None:
            try:
                relevant = bool(line.still_relevant())
            except Exception:  # noqa: BLE001 - a failing probe drops the line
                relevant = False
        if not relevant:
            self.stats.dropped_stale += 1
            logger.info("pipecat_voice_answer_first_stale_line kind=%s", line.kind)
        return relevant

    async def _release(self, line: _Line) -> None:
        self._released_texts.add(" ".join(line.text.split()).casefold())
        self.stats.released += 1
        self.stats.released_by_kind[line.kind] = self.stats.released_by_kind.get(line.kind, 0) + 1
        await self._speak(line.text, line.kind)

    async def release_due(self) -> bool:
        """Release the next line if its time has come. True when one was spoken."""
        while self._due():
            line = self._pending.pop(0)
            if not self._keep(line):
                continue
            self._awaiting_audio_since = self._clock()
            self._frames_at_release = self._playout.audio_frames if self._playout is not None else 0
            await self._release(line)
            return True
        return False

    async def run(self) -> None:
        """Release lines as the queued audio runs down, until cancelled."""
        while True:
            await self.release_due()
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self._poll_s)
            except (TimeoutError, asyncio.TimeoutError):
                pass

    async def finish_turn(self) -> None:
        """The brain is done: speak the held lines still relevant, in order.

        Normally nothing is held here (answer text dropped them). A turn that
        produced no answer text (only narration, e.g. a reported failure)
        still says what it decided to say.
        """
        while self._pending:
            line = self._pending.pop(0)
            if self._keep(line):
                await self._release(line)
