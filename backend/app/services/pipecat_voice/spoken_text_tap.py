"""Capture the text ElevenLabs actually spoke, for barge-in reconciliation.

``ElevenLabsInterruptReporter`` sits upstream of the TTS service so it can
accumulate the LLM draft. That placement means it can never observe
``TTSTextFrame``, which Pipecat's ``TTSService`` creates and pushes *downstream*
(tts -> transport.output() -> assistant_agg). Without a spoken-text signal the
reporter's reconciliation always degrades to "the whole draft was spoken", which
drops nothing.

This module closes that gap without reordering the existing processors: a tap
placed *after* ``transport.output()`` records ``TTSTextFrame`` into a ledger that
the upstream reporter reads on interrupt.

Placement matters. Word-level ``TTSTextFrame``s ride the transport's clock queue
and are released in playback order by ``transport.output()``, so tapping after
the output transport tracks real playback far more closely than tapping between
``tts`` and ``transport.output()`` (where queued-but-unplayed text would be
counted as already heard, over-claiming what the user received).
"""
from __future__ import annotations

from typing import Any

from pipecat.frames.frames import Frame, OutputAudioRawFrame, TTSTextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.core.logging import get_logger

logger = get_logger(__name__)


class SpokenTextLedger:
    """Per-turn accumulator of spoken text, plus a session-lifetime liveness flag.

    ``ever_recorded`` is deliberately NOT cleared by :meth:`reset`. It is the
    guard that keeps a broken or unwired tap from being mistaken for "nothing was
    spoken": an empty ledger only means silence if the tap has proven at least
    once that it receives frames. Without that distinction a routing regression
    would silently truncate every assistant turn to the empty string — a worse
    outcome than reconciling nothing at all.
    """

    __slots__ = ("_parts", "_ever_recorded")

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._ever_recorded = False

    def append(self, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            return
        self._parts.append(cleaned)
        self._ever_recorded = True

    def snapshot(self) -> str:
        """Spoken-so-far text for the current turn.

        Parts are joined with single spaces. Word-level frames may or may not
        carry inter-frame spacing (``includes_inter_frame_spaces``); reconciliation
        aligns on word tokens and ignores whitespace entirely, so normalising to
        spaces here is safe and avoids concatenating adjacent words together.
        """
        return " ".join(self._parts)

    @property
    def ever_recorded(self) -> bool:
        """True once any spoken text has been observed in this session."""
        return self._ever_recorded

    def reset(self) -> None:
        self._parts.clear()


class SpokenTextTapProcessor(FrameProcessor):
    """Pass-through processor recording TTSTextFrame text into a ledger.

    With a ``playback`` tracker (voice_reply_playback.VoicePlaybackTracker) it
    also records, per reply, the audio that left the output transport (the
    output transport pushes each audio frame downstream once it was written)
    and where each timed word fell in that audio. That is what maps the
    browser's played milliseconds back to text, and what tells filler audio
    from answer audio for first-speech latency.
    """

    def __init__(self, ledger: SpokenTextLedger, *, playback: Any | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ledger = ledger
        self._playback = playback

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TTSTextFrame):
            text = str(getattr(frame, "text", None) or "")
            self._ledger.append(text)
            if self._playback is not None and direction == FrameDirection.DOWNSTREAM:
                try:
                    self._playback.note_spoken_word(text)
                except Exception:  # noqa: BLE001 - accounting must never break playback
                    logger.debug("spoken_tap_playback_word_failed", exc_info=True)
        elif (
            self._playback is not None
            and isinstance(frame, OutputAudioRawFrame)
            and direction == FrameDirection.DOWNSTREAM
        ):
            try:
                self._playback.note_audio_frame(frame)
            except Exception:  # noqa: BLE001
                logger.debug("spoken_tap_playback_audio_failed", exc_info=True)
        await self.push_frame(frame, direction)
