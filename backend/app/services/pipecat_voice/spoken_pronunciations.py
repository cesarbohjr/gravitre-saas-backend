"""Spoken aliases: how written shorthand and product names should be said aloud.

Applied to every sentence just before it reaches TTS (after markdown and
delivery-tag stripping), so the transcript keeps the written form while the
voice says "for example" instead of "e g". Pure string work, no I/O, a few
microseconds per sentence.

Built-in aliases cover shorthand ElevenLabs Flash reads awkwardly. Product or
brand names whose pronunciation is a team choice (Gravitre itself, customer
names) come from ``VOICE_SPOKEN_ALIASES``, a JSON object of
``{"written": "spoken"}`` set on the backend, so they can change without a
deploy. Rewriting text here, not with an ElevenLabs pronunciation dictionary,
is deliberate: Pipecat deprecated dictionaries because server-side rewrites
break the word alignment the interrupt reporter relies on.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from app.core.logging import get_logger

logger = get_logger(__name__)

# Written form -> spoken form. Matched as whole words, case-sensitive.
BUILTIN_SPOKEN_ALIASES: dict[str, str] = {
    "e.g.": "for example",
    "i.e.": "that is",
    "etc.": "and so on",
    "vs.": "versus",
    "vs": "versus",
    "w/": "with",
    "w/o": "without",
    "&": "and",
    "SaaS": "sass",
    "approx.": "about",
    "FYI": "F Y I",
    "Gravitre": "Gravit tree",
}


def _compile(aliases: dict[str, str]) -> re.Pattern[str] | None:
    if not aliases:
        return None
    # Longest first so "w/o" wins over "w/".
    keys = sorted(aliases, key=len, reverse=True)
    alternation = "|".join(re.escape(k) for k in keys)
    # Word-ish boundaries that also work for keys ending in "." or "/".
    return re.compile(rf"(?<![\w.]){'(?:' + alternation + ')'}(?![\w/])")


@lru_cache(maxsize=8)
def _resolved(custom_json: str) -> tuple[dict[str, str], re.Pattern[str] | None]:
    aliases = dict(BUILTIN_SPOKEN_ALIASES)
    raw = (custom_json or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for written, spoken in parsed.items():
                    w, s = str(written).strip(), str(spoken).strip()
                    if w and s:
                        aliases[w] = s
        except (TypeError, ValueError):
            logger.warning("voice_spoken_aliases_invalid_json")
    return aliases, _compile(aliases)


def apply_spoken_aliases(text: str, custom_json: str | None = None) -> str:
    """Return ``text`` with written shorthand replaced by how it should sound."""
    if not text:
        return text
    aliases, pattern = _resolved(custom_json or "")
    if pattern is None:
        return text
    return pattern.sub(lambda m: aliases.get(m.group(0), m.group(0)), text)


__all__ = ["BUILTIN_SPOKEN_ALIASES", "apply_spoken_aliases"]
