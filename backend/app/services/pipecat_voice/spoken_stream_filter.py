"""Strip markdown from the client-facing ``assistant_text`` delta stream.

Measured in production 2026-09-08: voice replies reached the browser carrying raw
markdown — 12 ``**`` pairs on a tool-using turn, 6 on an orchestration turn —
e.g. ``"I planned a **2-step orchestration**:"`` and
``"Source: **assistant_workflow_runs**"``. The TTS branch was mostly protected
because ``split_speakable_chunks`` hands ``normalize_spoken_text`` whole
sentences, but the client branch pushed each raw LLM delta straight through.

Why a dedicated filter rather than calling ``normalize_spoken_text`` per delta:
a marker is routinely split across deltas (``"**comp"`` then ``"leted**"``), so
per-delta stripping would leave orphaned asterisks. And
``normalize_spoken_text`` collapses lines and appends terminal punctuation, which
is correct for a finished sentence going to TTS but would corrupt an incremental
stream.

This filter therefore withholds only the tail that could still be inside an
unclosed construct, emits everything before it with markers removed, and
preserves whitespace and newlines so words never glue together.
"""
from __future__ import annotations

import re

from app.services.voice_session_service import strip_markdown_inline

# Leading list/heading markers, stripped only at a confirmed line start.
_LEADING_FORMAT = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)")
_ASTERISK_RUN = re.compile(r"\*+")
# Markdown treats intra-word underscores as literal, so only word-boundary
# underscores can open emphasis.
_WORD_BOUNDARY_UNDERSCORE = re.compile(r"(?<![A-Za-z0-9_])_|_(?![A-Za-z0-9_])")


class SpokenMarkdownStreamFilter:
    """Incremental markdown stripper for streamed assistant text.

    Usage: ``feed(delta)`` per chunk, then ``flush()`` once the turn ends so a
    never-closed construct is still emitted rather than silently swallowed.
    """

    __slots__ = ("_pending", "_at_line_start")

    def __init__(self) -> None:
        self._pending = ""
        self._at_line_start = True

    def reset(self) -> None:
        self._pending = ""
        self._at_line_start = True

    @property
    def pending(self) -> str:
        """Text held back because a markdown construct may still be open."""
        return self._pending

    def feed(self, delta: str) -> str:
        self._pending += delta or ""
        safe_len = self._safe_prefix_len(self._pending)
        if safe_len <= 0:
            return ""
        safe = self._pending[:safe_len]
        self._pending = self._pending[safe_len:]
        return self._clean(safe)

    def flush(self) -> str:
        rest, self._pending = self._pending, ""
        return self._clean(rest) if rest else ""

    def _safe_prefix_len(self, text: str) -> int:
        """Length of the prefix containing no still-open markdown construct."""
        holds: list[int] = []

        # Backticks pair up; an odd count means one is still open.
        tick_positions = [i for i, ch in enumerate(text) if ch == "`"]
        if len(tick_positions) % 2 == 1:
            holds.append(tick_positions[-1])

        # Asterisk emphasis is delimited by runs of asterisks, so an odd number
        # of runs means the last one is still waiting for its partner.
        runs = list(_ASTERISK_RUN.finditer(text))
        if len(runs) % 2 == 1:
            holds.append(runs[-1].start())

        strikes = [m.start() for m in re.finditer(r"~~", text)]
        if len(strikes) % 2 == 1:
            holds.append(strikes[-1])
        # A lone trailing "~" may be the first half of an unseen "~~".
        if text.endswith("~") and not text.endswith("~~"):
            holds.append(len(text) - 1)

        underscores = [m.start() for m in _WORD_BOUNDARY_UNDERSCORE.finditer(text)]
        if len(underscores) % 2 == 1:
            holds.append(underscores[-1])

        # A link is only complete once its target closes.
        bracket = text.rfind("[")
        if bracket != -1:
            tail = text[bracket:]
            if not re.match(r"\[[^\]]*\]\([^)]*\)", tail):
                holds.append(bracket)

        return min(holds) if holds else len(text)

    def _clean(self, text: str) -> str:
        """Strip markers, handling line-leading markers at real line starts."""
        segments = text.split("\n")
        out: list[str] = []
        for index, segment in enumerate(segments):
            # index 0 continues whatever line the previous emit ended on; every
            # later segment provably follows a newline we just emitted.
            starts_line = self._at_line_start if index == 0 else True
            if starts_line:
                segment = _LEADING_FORMAT.sub("", segment)
            out.append(strip_markdown_inline(segment))

        result = "\n".join(out)
        if segments[-1].strip():
            self._at_line_start = False
        elif len(segments) > 1 or self._at_line_start:
            # Ended on a newline, or on whitespace while already at a line start.
            self._at_line_start = True
        return result
