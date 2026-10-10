"""Per-reply accounting of what was said, sent and played, by kind of speech.

A spoken reply is made of segments of three kinds:

* ``filler``   — an acknowledgement that carries no content ("One moment.").
* ``progress`` — tool narration describing real work ("Let me check your CRM.").
* ``answer``   — the reply itself (including a spoken refusal).

The LLM bridge labels each ``assistant_text`` delta with its kind. This module
keeps, for every reply id:

* **generated**: the labelled draft (the client text, in order) and its segments;
* **sent**: audio that left the output transport (sample counts at the tap) and,
  for each word ElevenLabs timed, how much audio had been sent when that word's
  frame passed the tap;
* **played**: what the browser reports through ``playback.progress``;
* **interrupted**: whether a barge-in cut the reply.

From that it answers two questions: when the first audio of each kind went
out (first-speech latency must use the answer, not the filler), and which
answer text was heard when a reply was cut (history must hold only that).

Played ms -> text uses the word timings: a word counts as heard once the audio
sent before its frame (the audio that precedes its start) has been played.
Without word timings it spreads the characters evenly over the reply's sent
audio. Both map to a character offset in the draft, which the segments turn
into answer-only text.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.logging import get_logger

logger = get_logger(__name__)

FILLER = "filler"
PROGRESS = "progress"
ANSWER = "answer"
SEGMENT_KINDS = (FILLER, PROGRESS, ANSWER)

# Appended to a stored assistant message that a barge-in cut, so the model
# knows the user did not hear the rest (it otherwise reads the cut text as a
# finished answer and never repeats the part that was lost).
TRUNCATION_MARKER = "[interrupted: the user did not hear the rest of this reply]"
NOTHING_HEARD_MARKER = "[interrupted: the user did not hear this reply]"

# How long the interrupt bookkeeping waits for the browser's report of what it
# played. The browser sends it on receipt of speech.interrupted, so one round
# trip plus scheduling; past this the server-side estimate is used.
CLIENT_REPORT_WAIT_S = 1.2
# Attribute ReplyAudioStampProcessor sets on each outbound audio frame: the
# reply that generated it (json_audio_serializer.REPLY_ID_ATTR; repeated here so
# this module stays free of pipecat imports, and pinned equal by a test).
AUDIO_REPLY_ID_ATTR = "gravitre_reply_id"
# Replies remembered per socket.
MAX_REPLIES = 8
# Report values outside this range are ignored (ms).
_MAX_REPORT_MS = 30 * 60 * 1000

# Same word tokens as voice_conversational_polish.reconcile_played_audio.
_WORD_RE = re.compile(r"[\w'’-]+")
# Punctuation that stays with the word it follows.
_TRAILING_PUNCT = set(".,!?;:…\"')]}")
# How far ahead a spoken word may re-find its place in the draft after the
# spoken form diverged (numbers, aliases).
_ALIGN_LOOKAHEAD = 6


def normalize_segment_kind(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    return value if value in SEGMENT_KINDS else ANSWER


@dataclass
class DraftSegment:
    kind: str
    start: int
    end: int


def _append_segment(segments: list[DraftSegment], kind: str, start: int, end: int) -> None:
    if end <= start:
        return
    if segments and segments[-1].kind == kind and segments[-1].end == start:
        segments[-1].end = end
        return
    segments.append(DraftSegment(kind=kind, start=start, end=end))


def text_for_kinds(
    draft: str, segments: list[DraftSegment], upto: int | None, kinds: frozenset[str] | set[str]
) -> str:
    """Text of ``kinds`` segments, clipped at character ``upto`` of ``draft``."""
    limit = len(draft) if upto is None else max(0, min(int(upto), len(draft)))
    pieces: list[str] = []
    for seg in segments:
        if seg.kind not in kinds or seg.start >= limit:
            continue
        piece = draft[seg.start : min(seg.end, limit)].strip()
        if piece:
            pieces.append(piece)
    return " ".join(pieces).strip()


def snap_to_word_end(draft: str, offset: int) -> int:
    """Move ``offset`` to the end of the word it falls in, plus trailing punctuation."""
    offset = max(0, min(int(offset), len(draft)))
    while offset < len(draft) and offset > 0 and _WORD_RE.match(draft[offset]) and _WORD_RE.match(draft[offset - 1]):
        offset += 1
    while offset < len(draft) and draft[offset] in _TRAILING_PUNCT:
        offset += 1
    return offset


@dataclass
class ReplyPlayback:
    """Generated / sent / played / interrupted accounting for one reply."""

    reply_id: int | None = None
    draft: str = ""
    segments: list[DraftSegment] = field(default_factory=list)
    # Audio that passed the output transport, in ms.
    sent_audio_ms: float = 0.0
    # (sent audio ms when the word frame passed the tap, draft char end of the word)
    word_marks: list[tuple[float, int]] = field(default_factory=list)
    spoken_words: int = 0
    first_audio_at: dict[str, float] = field(default_factory=dict)
    first_audio_sent_ms: dict[str, float] = field(default_factory=dict)
    # Browser reports.
    client_received_ms: float | None = None
    client_played_ms: float | None = None
    client_interrupted: bool = False
    client_reports: int = 0
    # Server-side barge-in.
    interrupted: bool = False
    _tokens: list[tuple[str, int]] = field(default_factory=list)
    _tokens_for_len: int = -1
    _cursor: int = 0
    _last_char_end: int = 0
    _report_event: asyncio.Event | None = None

    # ---- generated ---------------------------------------------------------
    def add_text(self, delta: str, kind: str = ANSWER) -> None:
        if not delta:
            return
        start = len(self.draft)
        self.draft += delta
        _append_segment(self.segments, normalize_segment_kind(kind), start, len(self.draft))

    def kind_at(self, offset: int) -> str | None:
        for seg in self.segments:
            if seg.start <= offset < seg.end:
                return seg.kind
        if self.segments and offset >= self.segments[-1].end:
            return self.segments[-1].kind
        return None

    def has_non_answer(self) -> bool:
        return any(seg.kind != ANSWER for seg in self.segments)

    def answer_text_upto(self, offset: int | None) -> str:
        return text_for_kinds(self.draft, self.segments, offset, {ANSWER})

    def non_answer_texts(self) -> list[str]:
        return [
            self.draft[seg.start : seg.end].strip()
            for seg in self.segments
            if seg.kind != ANSWER and self.draft[seg.start : seg.end].strip()
        ]

    # ---- sent ----------------------------------------------------------------
    def note_audio(self, num_bytes: int, sample_rate: int, num_channels: int = 1) -> None:
        if num_bytes <= 0 or sample_rate <= 0:
            return
        frames = num_bytes / (2 * max(1, int(num_channels)))
        self.sent_audio_ms += frames * 1000.0 / float(sample_rate)

    def _draft_tokens(self) -> list[tuple[str, int]]:
        if self._tokens_for_len != len(self.draft):
            self._tokens = [(m.group(0).casefold(), m.end()) for m in _WORD_RE.finditer(self.draft)]
            self._tokens_for_len = len(self.draft)
        return self._tokens

    def note_spoken_word(self, text: str, at: float) -> list[str]:
        """Record a TTS word frame that just passed the output transport.

        Returns the kinds whose first audio this word is.
        """
        new_kinds: list[str] = []
        for match in _WORD_RE.finditer(text or ""):
            word = match.group(0).casefold()
            tokens = self._draft_tokens()
            found = None
            for idx in range(self._cursor, min(len(tokens), self._cursor + _ALIGN_LOOKAHEAD)):
                if tokens[idx][0] == word:
                    found = idx
                    break
            if found is not None:
                self._cursor = found + 1
                self._last_char_end = tokens[found][1]
            # A word whose spoken form differs from the draft ("$5" -> "five
            # dollars") keeps the last aligned position: never over-claim.
            self.spoken_words += 1
            self.word_marks.append((self.sent_audio_ms, self._last_char_end))
            # Which segment is being spoken: the token being aligned next, or
            # the one just aligned.
            probe = self._last_char_end - 1 if found is not None else (
                tokens[self._cursor][1] - 1 if self._cursor < len(tokens) else self._last_char_end - 1
            )
            kind = self.kind_at(max(0, probe)) if self.segments else ANSWER
            if kind and kind not in self.first_audio_at:
                self.first_audio_at[kind] = at
                self.first_audio_sent_ms[kind] = self.sent_audio_ms
                new_kinds.append(kind)
        return new_kinds

    # ---- played ----------------------------------------------------------------
    def apply_client_report(self, report: dict[str, Any]) -> bool:
        played = _ms_or_none(report.get("played_ms"))
        received = _ms_or_none(report.get("received_ms"))
        if played is None and received is None:
            return False
        if played is not None:
            self.client_played_ms = max(self.client_played_ms or 0.0, played)
        if received is not None:
            self.client_received_ms = max(self.client_received_ms or 0.0, received)
        self.client_reports += 1
        if bool(report.get("interrupted")):
            self.client_interrupted = True
            if self._report_event is not None:
                self._report_event.set()
        return True

    def char_offset_for_played_ms(self, played_ms: float) -> tuple[int, str]:
        """Draft offset heard after ``played_ms`` of this reply's audio, and the method."""
        played = max(0.0, float(played_ms))
        if self.word_marks:
            heard = 0
            for sent_at, char_end in self.word_marks:
                # The word's audio starts at sent_at; it is heard once that much
                # audio has played (with a few ms of slack for frame rounding).
                if sent_at <= played + 5.0:
                    heard = max(heard, char_end)
                else:
                    break
            return snap_to_word_end(self.draft, heard), "word_timings"
        if self.sent_audio_ms > 0:
            share = min(1.0, played / self.sent_audio_ms)
            return snap_to_word_end(self.draft, int(len(self.draft) * share)), "char_spread"
        return 0, "no_audio"

    def summary(self) -> dict[str, Any]:
        return {
            "reply_id": self.reply_id,
            "generated_chars": len(self.draft),
            "segments": [
                {"kind": s.kind, "chars": s.end - s.start} for s in self.segments
            ],
            "sent_audio_ms": int(round(self.sent_audio_ms)),
            "spoken_words": self.spoken_words,
            "client_received_ms": _round(self.client_received_ms),
            "client_played_ms": _round(self.client_played_ms),
            "client_interrupted": self.client_interrupted,
            "client_reports": self.client_reports,
            "interrupted": self.interrupted,
        }


def _round(value: float | None) -> int | None:
    return int(round(value)) if value is not None else None


def _ms_or_none(value: Any) -> float | None:
    try:
        ms = float(value)
    except (TypeError, ValueError):
        return None
    if ms != ms or ms < 0 or ms > _MAX_REPORT_MS:
        return None
    return ms


FirstAudioCallback = Callable[[str, float, int | None], None]


class VoicePlaybackTracker:
    """All replies of one voice socket, keyed by the session's reply id."""

    def __init__(
        self,
        *,
        reply_id_getter: Callable[[], int | None] | None = None,
        clock: Callable[[], float] = time.perf_counter,
        monotonic: Callable[[], float] = time.monotonic,
        on_first_audio: FirstAudioCallback | None = None,
    ) -> None:
        self._reply_id_getter = reply_id_getter
        self._clock = clock
        self._monotonic = monotonic
        self._replies: dict[int, ReplyPlayback] = {}
        self._on_first_audio = on_first_audio
        # Spoken filler/progress sentences of this socket, for cleaning the
        # in-socket context (see strip_non_answer_speech).
        self._non_answer_phrases: list[str] = []
        self.last_audio_activity: float | None = None
        # Reply of the last audio frame played out, from the stamp on the frame.
        # Words and audio after the output transport belong to the reply being
        # heard, which can be older than the session's current reply id (a cut
        # reply's tail, or the next reply already generating).
        self._audio_reply_id: int | None = None

    def set_first_audio_callback(self, callback: FirstAudioCallback | None) -> None:
        self._on_first_audio = callback

    def current_reply_id(self) -> int | None:
        if self._reply_id_getter is None:
            return None
        try:
            value = self._reply_id_getter()
        except Exception:  # noqa: BLE001
            return None
        return value if isinstance(value, int) else None

    def reply(self, reply_id: int | None = None, *, create: bool = True) -> ReplyPlayback | None:
        rid = reply_id if reply_id is not None else self.current_reply_id()
        if rid is None:
            return None
        found = self._replies.get(rid)
        if found is None and create:
            found = ReplyPlayback(reply_id=rid)
            self._replies[rid] = found
            for old in sorted(self._replies)[:-MAX_REPLIES]:
                self._replies.pop(old, None)
        return found

    # ---- feeds -----------------------------------------------------------------
    def note_assistant_text(self, delta: str, kind: str, reply_id: int | None = None) -> ReplyPlayback | None:
        reply = self.reply(reply_id)
        if reply is None:
            return None
        kind = normalize_segment_kind(kind)
        reply.add_text(delta, kind)
        if kind != ANSWER:
            phrase = (delta or "").strip()
            if phrase and phrase not in self._non_answer_phrases:
                self._non_answer_phrases.append(phrase)
                self._non_answer_phrases = self._non_answer_phrases[-32:]
        return reply

    def audio_reply_id(self) -> int | None:
        """Reply whose audio is being played out (stamped), else the current reply."""
        if self._audio_reply_id is not None:
            return self._audio_reply_id
        return self.current_reply_id()

    def note_spoken_word(self, text: str) -> None:
        reply = self.reply(self.audio_reply_id(), create=False)
        if reply is None:
            return
        at = self._clock()
        for kind in reply.note_spoken_word(text, at):
            if self._on_first_audio is not None:
                try:
                    self._on_first_audio(kind, at, reply.reply_id)
                except Exception:  # noqa: BLE001 - metrics must never break playback
                    logger.debug("voice_playback_first_audio_callback_failed", exc_info=True)

    def note_audio_frame(self, frame: Any) -> None:
        audio = getattr(frame, "audio", None) or b""
        self.last_audio_activity = self._monotonic()
        stamped = getattr(frame, AUDIO_REPLY_ID_ATTR, None)
        if isinstance(stamped, int) and not isinstance(stamped, bool):
            self._audio_reply_id = stamped
        reply = self.reply(self.audio_reply_id(), create=False)
        if reply is None:
            return
        reply.note_audio(
            len(audio),
            int(getattr(frame, "sample_rate", None) or 0),
            int(getattr(frame, "num_channels", None) or 1),
        )

    def note_client_report(self, msg: dict[str, Any]) -> bool:
        """A ``playback.progress`` message from the browser."""
        raw = msg.get("reply_id")
        if not isinstance(raw, int) or isinstance(raw, bool):
            return False
        reply = self.reply(raw, create=False)
        if reply is None:
            return False
        return reply.apply_client_report(msg)

    def mark_interrupted(self, reply_id: int | None) -> ReplyPlayback | None:
        reply = self.reply(reply_id, create=False) if reply_id is not None else None
        if reply is not None:
            reply.interrupted = True
            if reply._report_event is None:
                reply._report_event = asyncio.Event()
                if reply.client_interrupted:
                    reply._report_event.set()
        return reply

    async def wait_for_client_report(
        self, reply_id: int | None, timeout_s: float = CLIENT_REPORT_WAIT_S
    ) -> ReplyPlayback | None:
        """The reply once the browser reported where its interrupted playback stopped."""
        reply = self.reply(reply_id, create=False) if reply_id is not None else None
        if reply is None:
            return None
        if reply.client_interrupted:
            return reply
        if reply._report_event is None:
            reply._report_event = asyncio.Event()
        try:
            await asyncio.wait_for(reply._report_event.wait(), timeout=max(0.0, timeout_s))
        except (TimeoutError, asyncio.TimeoutError):
            return None
        return reply if reply.client_interrupted else None

    def non_answer_phrases(self) -> list[str]:
        return list(self._non_answer_phrases)


def strip_non_answer_speech(text: str, phrases: list[str]) -> str:
    """Remove spoken filler/progress sentences from an assistant context message.

    The in-socket context gets the reply's spoken words, filler and tool
    narration included, while the stored message holds the answer only. Left
    in, "Sure, let me look. Let me check your CRM." reads to the model as part
    of its answer, and the context and the stored row no longer match. Matching
    is on word tokens, so punctuation and spacing differences do not matter.
    """
    if not text or not phrases:
        return text
    spans = [(m.start(), m.end(), m.group(0).casefold()) for m in _WORD_RE.finditer(text)]
    words = [w for _, _, w in spans]
    remove = [False] * len(spans)
    for phrase in phrases:
        target = [m.group(0).casefold() for m in _WORD_RE.finditer(phrase or "")]
        if not target or len(target) > len(words):
            continue
        i = 0
        while i <= len(words) - len(target):
            if words[i : i + len(target)] == target and not any(remove[i : i + len(target)]):
                for j in range(i, i + len(target)):
                    remove[j] = True
                i += len(target)
            else:
                i += 1
    if not any(remove):
        return text
    out: list[str] = []
    cursor = 0
    for (start, end, _), drop in zip(spans, remove):
        if drop:
            out.append(text[cursor:start])
            # Skip the word and the punctuation that belongs to it.
            cursor = end
            while cursor < len(text) and text[cursor] in _TRAILING_PUNCT:
                cursor += 1
    out.append(text[cursor:])
    cleaned = " ".join("".join(out).split())
    return cleaned.lstrip(" ,.;:")
