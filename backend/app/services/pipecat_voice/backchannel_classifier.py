"""Real, rule-based backchannel-vs-interruption classifier for live voice turns.

Conversational-realism Phase 1. Classifies a short user utterance that arrives
while the agent is speaking into one of a closed set of categories:

    BACKCHANNEL   - short affirming utterance ("yeah", "uh-huh", "right") that
                    must NOT stop agent speech.
    STOP_COMMAND  - explicit request to stop/pause/cancel.
    CORRECTION    - the user is correcting something the agent just said.
    NEW_QUESTION  - the user is asking something new.
    INTERRUPTION  - default/fallback: genuinely new content that should
                    displace the agent's turn.

Deliberately rule-based and deterministic (no LLM call in this hot, latency
critical path) per the prompt's own instruction to reuse Deepgram's native
signals rather than build a heavyweight classifier from scratch. The closed
word lists below ARE the whole mechanism, kept small and easy to mutation-test.
"""
from __future__ import annotations

import re
from enum import Enum

__all__ = [
    "BackchannelClassification",
    "classify_user_utterance",
    "is_backchannel",
]


class BackchannelClassification(str, Enum):
    """Closed set of turn-taking classifications for an in-progress user turn."""

    BACKCHANNEL = "backchannel"
    STOP_COMMAND = "stop_command"
    CORRECTION = "correction"
    NEW_QUESTION = "new_question"
    INTERRUPTION = "interruption"


# Closed vocabulary of short affirming utterances. An utterance classifies as
# BACKCHANNEL only if EVERY token in it (after normalization) is drawn from
# this set - a single extra real word ("yeah but wait") falls through to the
# other rules below, which is the correct, safe behavior.
_BACKCHANNEL_PHRASES: frozenset[str] = frozenset(
    {
        "yeah",
        "yep",
        "yup",
        "yes",
        "uhhuh",
        "mhm",
        "mmhmm",
        "mm",
        "right",
        "okay",
        "ok",
        "sure",
        "got it",
        "gotcha",
        "i see",
        "cool",
        "alright",
        "all right",
        "makes sense",
        "fair enough",
        "understood",
        "noted",
        "good",
        "great",
        "nice",
        "uh huh",
    }
)

# Max word count for something to even be considered for BACKCHANNEL. A real
# backchannel is always short; this is a cheap, honest guard against a long
# utterance that happens to start with "yeah" ("yeah but I actually need...").
_BACKCHANNEL_MAX_WORDS = 3

_STOP_PHRASES: frozenset[str] = frozenset(
    {
        "stop",
        "wait",
        "hold on",
        "hang on",
        "pause",
        "cancel",
        "cancel that",
        "never mind",
        "nevermind",
        "stop talking",
        "shut up",
        "quiet",
        "enough",
    }
)

_CORRECTION_PREFIXES: tuple[str, ...] = (
    "no ",
    "no,",
    "actually",
    "wait no",
    "that's wrong",
    "thats wrong",
    "that's not right",
    "thats not right",
    "that's not what i",
    "i meant",
    "not that",
    "no i said",
    "no that's",
    "no thats",
)

_QUESTION_WORDS: tuple[str, ...] = (
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "can you",
    "could you",
    "would you",
    "will you",
    "is it",
    "does it",
    "do you",
)

_WORD_RE = re.compile(r"[a-z']+")


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation-as-separators, collapse whitespace."""
    lowered = (text or "").strip().lower()
    # Keep apostrophes (for "that's"), drop everything else non-alnum as a
    # word boundary so "uh-huh," "uh_huh" etc all normalize the same way.
    tokens = _WORD_RE.findall(lowered.replace("-", " ").replace("_", " "))
    return " ".join(tokens)


def is_backchannel(classification: BackchannelClassification) -> bool:
    """True only for the one classification that must never stop agent speech."""
    return classification is BackchannelClassification.BACKCHANNEL


def classify_user_utterance(text: str) -> BackchannelClassification:
    """Classify a user utterance overlapping agent speech.

    Real, closed-set, deterministic classification. Falls back to
    INTERRUPTION (the safe default - stop and listen) whenever the utterance
    does not confidently match a more specific category. Never guesses
    BACKCHANNEL on ambiguous input.
    """
    normalized = _normalize(text)
    if not normalized:
        # No transcript yet - caller decides based on timing; this function
        # only classifies text it actually has.
        return BackchannelClassification.INTERRUPTION

    words = normalized.split()

    # STOP COMMAND - checked first: "stop" said mid-backchannel-like utterance
    # must never be swallowed as an affirmation.
    if normalized in _STOP_PHRASES or (len(words) <= 3 and words[0] in {"stop", "wait", "pause", "cancel"}):
        return BackchannelClassification.STOP_COMMAND

    # CORRECTION - the user is actively correcting the agent.
    if any(normalized.startswith(prefix.rstrip(",")) for prefix in _CORRECTION_PREFIXES):
        return BackchannelClassification.CORRECTION

    # BACKCHANNEL - short, closed-vocabulary affirmation only.
    if len(words) <= _BACKCHANNEL_MAX_WORDS and normalized in _BACKCHANNEL_PHRASES:
        return BackchannelClassification.BACKCHANNEL
    # Also allow simple repeats/combinations of backchannel tokens, e.g.
    # "yeah okay" or "right right" - still every token from the closed set.
    if len(words) <= _BACKCHANNEL_MAX_WORDS and words and all(
        w in _BACKCHANNEL_PHRASES for w in words
    ):
        return BackchannelClassification.BACKCHANNEL

    # NEW QUESTION - contains a question word/phrase, or ends with "?".
    if text.strip().endswith("?") or any(
        normalized == qw or normalized.startswith(qw + " ") for qw in _QUESTION_WORDS
    ):
        return BackchannelClassification.NEW_QUESTION

    # Default: genuinely new content. Treat as a real interruption.
    return BackchannelClassification.INTERRUPTION
