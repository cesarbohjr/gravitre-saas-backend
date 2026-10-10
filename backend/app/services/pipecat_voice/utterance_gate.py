"""Only a real user utterance may start a voice turn.

Opening Talk must never produce an answer the user did not ask for. The live
STT can finalize a "turn" out of a cough, a breath, an "uh" or room noise right
after the mic opens; before this gate that text went straight to the user
aggregator and the brain answered it using whatever was most salient in the
conversation (a trailing unanswered question, an earlier offer, org context).

``is_non_utterance`` is the single decision. ``UtteranceGateProcessor`` applies
it to final STT transcripts before anything downstream (transcript relay,
speculative generation, user aggregator) sees them. A dropped transcript leaves
the user aggregator empty, so Pipecat's own turn-stop pushes no LLM context and
no brain turn runs. Text the user typed in this socket (``user_id="browser"``)
is an explicit message and is never gated.
"""
from __future__ import annotations

import re
from typing import Any

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.core.logging import get_logger

logger = get_logger(__name__)

# Hesitations and non-lexical sounds. Repeated letters are folded first, so
# "ummm" and "hmmmm" match. "uh-huh"/"mm-hmm" are here too: with nothing on the
# table they ask for nothing, and they must never count as a yes to an old offer.
# "huh?" is left out on purpose: mid-conversation it means "say that again".
_FILLER_TOKEN_RE = re.compile(
    r"^(?:u+h*|u+m+|u+h+m+|e+r+m*|e+h+|a+h+|a+w+|o+h+|o+o+h+|h+m+|m+|m+h+m+|"
    r"uh-?huh|mm-?hmm|mhm|uh-?oh|ha|psst|shh+|tsk)$"
)
_TOKEN_RE = re.compile(r"[a-z0-9'-]+")

# Below this average word confidence a short transcript is treated as noise.
DEFAULT_MIN_SHORT_TRANSCRIPT_CONFIDENCE = 0.45
# "Short" for the confidence floor: long low-confidence speech is still speech.
SHORT_TRANSCRIPT_MAX_WORDS = 3


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def is_filler_only(text: str) -> bool:
    """True when the text has no content beyond hesitation sounds."""
    tokens = [t.strip("'-") for t in _tokens(text)]
    tokens = [t for t in tokens if t]
    if not tokens:
        return True
    # "uh huh" / "mm hmm" arrive as two tokens; fold them into one.
    folded = re.sub(r"\b(?:uh[\s-]+huh|mm+[\s-]+hmm+)\b", "mhm", " ".join(tokens))
    return all(_FILLER_TOKEN_RE.match(t) for t in folded.split())


def average_word_confidence(result: Any) -> float | None:
    """Mean per-word confidence from a Deepgram result payload, when present."""
    if not isinstance(result, dict):
        return None
    words = result.get("words")
    if not isinstance(words, list):
        channel = result.get("channel")
        alts = channel.get("alternatives") if isinstance(channel, dict) else None
        first = alts[0] if isinstance(alts, list) and alts and isinstance(alts[0], dict) else {}
        words = first.get("words")
    if not isinstance(words, list):
        return None
    values = [
        float(w["confidence"])
        for w in words
        if isinstance(w, dict) and isinstance(w.get("confidence"), (int, float))
    ]
    if not values:
        return None
    return sum(values) / len(values)


def is_non_utterance(
    text: str,
    *,
    confidence: float | None = None,
    min_confidence: float = DEFAULT_MIN_SHORT_TRANSCRIPT_CONFIDENCE,
) -> bool:
    """True when ``text`` is not a request a turn may answer.

    Empty, punctuation-only, single-letter and filler-only transcripts never
    are. A short transcript whose recognizer confidence is below the floor is
    treated as noise.
    """
    stripped = (text or "").strip()
    if not stripped:
        return True
    if not re.search(r"[A-Za-z0-9]", stripped):
        return True
    tokens = _tokens(stripped)
    if len(tokens) == 1 and len(tokens[0]) == 1 and not tokens[0].isdigit():
        return True
    if is_filler_only(stripped):
        return True
    return (
        confidence is not None
        and min_confidence > 0
        and len(tokens) <= SHORT_TRANSCRIPT_MAX_WORDS
        and confidence < min_confidence
    )


def min_short_transcript_confidence(settings: Any) -> float:
    raw = getattr(settings, "voice_min_short_transcript_confidence", None)
    try:
        return float(raw) if raw is not None else DEFAULT_MIN_SHORT_TRANSCRIPT_CONFIDENCE
    except (TypeError, ValueError):
        return DEFAULT_MIN_SHORT_TRANSCRIPT_CONFIDENCE


class UtteranceGateProcessor(FrameProcessor):
    """Drop final STT transcripts that are not a real utterance."""

    def __init__(
        self,
        *,
        app_settings: Any = None,
        org_id: str = "",
        voice_session: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._min_confidence = min_short_transcript_confidence(app_settings)
        self._org_id = org_id
        # Told about dropped filler so a held barge-in made only of "mm-hmm"
        # resolves as a backchannel instead of an empty interruption.
        self._voice_session = voice_session
        self.dropped = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if (
            direction == FrameDirection.DOWNSTREAM
            and isinstance(frame, TranscriptionFrame)
            and str(getattr(frame, "user_id", "") or "") != "browser"
        ):
            text = str(getattr(frame, "text", "") or "")
            confidence = average_word_confidence(getattr(frame, "result", None))
            if is_non_utterance(text, confidence=confidence, min_confidence=self._min_confidence):
                self.dropped += 1
                note = getattr(self._voice_session, "note_filler_dropped", None)
                if callable(note) and is_filler_only(text):
                    note()
                logger.info(
                    "pipecat_voice_non_utterance_dropped org_id=%s chars=%s confidence=%s",
                    self._org_id,
                    len(text.strip()),
                    None if confidence is None else round(confidence, 3),
                )
                return
        await self.push_frame(frame, direction)
