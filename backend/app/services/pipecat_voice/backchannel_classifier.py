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
    "InterruptIntent",
    "classify_interrupt_intent",
    "could_become_speech_stop",
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


# --- Interruption intents (voice_interrupt_intents_v1) ------------------------
#
# What the user wants done about the reply and the work behind it, on top of
# the turn-taking class above. Same rules engine, same normalization; still no
# model call per acoustic event. Anything not matched confidently is NEW_REQUEST,
# which keeps today's behaviour (stop the reply, answer the new turn), and a
# bare "stop" / "wait" stays a plain stop: reading it as "silence only" would
# let a write the user meant to halt go through.


class InterruptIntent(str, Enum):
    BACKCHANNEL = "backchannel"
    EXPLAIN = "explain"
    CORRECTION = "correction"
    SPEECH_STOP = "speech_stop"
    TASK_CANCEL = "task_cancel"
    STOP = "stop"
    NEW_REQUEST = "new_request"


_LEAD_IN = r"(?:(?:ok(?:ay)?|oh|um+|uh+|so|hey|sorry|wait|hold\s+on|hang\s+on|please)\s+)*"
_TRAIL = r"(?:\s+(?:please|thanks|thank\s+you|now|for\s+now|then))*"

# Silence the reply; the work behind it carries on.
_SPEECH_STOP_CORE = (
    r"(?:stop|quit)\s+(?:talking|speaking|reading(?:\s+(?:it|that|this))?(?:\s+out)?)|"
    r"(?:you\s+can\s+)?(?:be\s+quiet|quiet\s+down|hush|shush|shut\s+up|mute|go\s+quiet)|"
    r"(?:that'?s\s+)?enough\s+talking|"
    r"(?:no\s+need\s+to|you\s+don'?t\s+(?:need|have)\s+to)\s+(?:read|say|talk\s+through)\s+(?:it|that|this|all\s+that)(?:\s+out(?:\s+loud)?)?|"
    r"(?:don'?t|do\s+not)\s+(?:read|say)\s+(?:it|that|this)(?:\s+out(?:\s+loud)?)?"
)
_KEEP_WORKING = (
    r"(?:\s*(?:,|and|but|just)?\s*(?:keep|carry\s+on|continue|go\s+on)"
    r"(?:\s+(?:working|going))?"
    r"(?:\s+(?:on\s+(?:it|that)|with\s+(?:it|that|the\s+\w+)|in\s+the\s+background|quietly|silently))?)"
)
_SPEECH_STOP_RE = re.compile(rf"^{_LEAD_IN}(?:you\s+can\s+)?(?:{_SPEECH_STOP_CORE}){_TRAIL}{_KEEP_WORKING}?{_TRAIL}$")
_KEEP_WORKING_ONLY_RE = re.compile(
    rf"^{_LEAD_IN}(?:just\s+)?(?:keep|carry\s+on)\s+(?:working|going)\s+(?:quietly|silently|in\s+the\s+background)$"
)

# Stop the work: nothing further may be committed.
_TASK_CANCEL_RE = re.compile(
    rf"^{_LEAD_IN}(?:no\s+)?(?:"
    r"cancel(?:\s+(?:it|that|this|everything|the\s+\w+(?:\s+\w+)?))?|"
    r"(?:don'?t|do\s+not)\s+(?:send|post|publish|submit|do|run|book|schedule|create|delete|update|email|go\s+ahead\s+with)"
    r"(?:\s+(?:it|that|this|them|anything|the\s+\w+(?:\s+\w+)?))?|"
    r"abort(?:\s+(?:it|that|this))?|call\s+(?:it|that)\s+off|scrap\s+(?:it|that|this)|"
    r"stop\s+(?:it|that|this|the\s+\w+|sending(?:\s+it)?|everything|what\s+you'?re\s+doing)|"
    r"forget\s+(?:it|that|about\s+it)|never\s*mind"
    rf"){_TRAIL}$"
)

_CANCEL_ANYWHERE_RE = re.compile(
    r"\b(?:cancel\s+(?:it|that|this|the\s+\w+)|(?:don'?t|do\s+not)\s+send|abort)\b"
)

# Pause and explain what was just said; the task stays as it was.
_EXPLAIN_RE = re.compile(
    rf"^{_LEAD_IN}(?:"
    r"(?:can\s+you\s+|could\s+you\s+)?explain"
    r"(?:\s+(?:that|this|it|those|these|the|what\s+you\s+(?:mean|meant|said))(?:\s+\w+){0,3})?|"
    r"what\s+(?:does|did)\s+(?:that|this|it|the\s+\w+)\s+mean|"
    r"what\s+do\s+you\s+mean(?:\s+by\s+(?:that|this|it))?|"
    r"what(?:'s|\s+is)\s+(?:that|this)(?:\s+(?:number|figure|metric|one))?|"
    r"where\s+(?:does|did)\s+(?:that|this|the)\s*(?:\w+\s+)?(?:number|figure|data|stat)?\s*come\s+from|"
    r"how\s+did\s+you\s+(?:get|calculate|work\s+out|come\s+up\s+with)\s+(?:that|this|it|the\s+\w+)|"
    r"why\s+(?:is|was|did)\s+(?:that|this|it)(?:\s+\w+){0,4}"
    rf"){_TRAIL}$"
)

# Revise the active request instead of starting a new one.
_CORRECTION_RE = re.compile(
    rf"^{_LEAD_IN}(?:"
    r"(?:no|nope|actually|not\s+that)\b.+|"
    r"(?:i\s+meant|i\s+said)\b.+|"
    r"(?:use|make\s+it|change\s+(?:it|that)\s+to|switch\s+(?:it\s+)?to|go\s+with|try)\s+.+|"
    r".+\binstead(?:\s+of\s+.+)?|"
    r".+\b(?:not|rather\s+than)\s+\w+"
    r")$"
)
_MURMUR_TOKENS = frozenset({"mm", "mmm", "hmm", "mhmm", "uh", "huh", "ah", "aha", "oh"})

# A correction is short; a long "no ..." is usually a new request.
_CORRECTION_MAX_WORDS = 14

_SPEECH_STOP_STARTERS: tuple[tuple[str, ...], ...] = (
    ("stop", "talking"),
    ("stop", "speaking"),
    ("stop", "reading"),
    ("be", "quiet"),
    ("shut", "up"),
    ("no", "need", "to"),
    ("you", "can", "stop", "talking"),
    ("you", "can", "be", "quiet"),
)


def could_become_speech_stop(text: str) -> bool:
    """True for interim text that is still only the start of a speech-only stop.

    "stop" may become "stop talking, keep working"; deciding on the first
    word would cancel the work the rest of the sentence asks to keep.
    """
    words = _normalize(text).split()
    words = [w for w in words if w not in {"okay", "ok", "please", "oh", "um", "uh", "so"}]
    if not words or len(words) > 4:
        return False
    return any(tuple(words) == starter[: len(words)] for starter in _SPEECH_STOP_STARTERS) and not any(
        tuple(words) == starter for starter in _SPEECH_STOP_STARTERS
    )


def classify_interrupt_intent(text: str) -> InterruptIntent:
    """Intent of speech that overlapped the reply (or the work before it).

    Ordered from most to least protective of the user's work: an explicit
    cancel wins over everything, a speech-only stop must be explicit, and
    anything ambiguous falls back to today's behaviour.
    """
    normalized = _normalize(text)
    if not normalized:
        return InterruptIntent.NEW_REQUEST
    words = normalized.split()
    if _TASK_CANCEL_RE.match(normalized) or (
        len(words) <= 8 and _CANCEL_ANYWHERE_RE.search(normalized)
    ):
        # "stop talking and cancel it" cancels: the safer reading wins.
        return InterruptIntent.TASK_CANCEL
    if _SPEECH_STOP_RE.match(normalized) or _KEEP_WORKING_ONLY_RE.match(normalized):
        return InterruptIntent.SPEECH_STOP
    base = classify_user_utterance(text)
    if base is BackchannelClassification.BACKCHANNEL:
        return InterruptIntent.BACKCHANNEL
    if len(words) <= _BACKCHANNEL_MAX_WORDS and all(
        w in _BACKCHANNEL_PHRASES or w in _MURMUR_TOKENS for w in words
    ):
        # "mm-hmm" normalizes to "mm hmm", which the closed set above misses.
        return InterruptIntent.BACKCHANNEL
    if _EXPLAIN_RE.match(normalized):
        return InterruptIntent.EXPLAIN
    if base is BackchannelClassification.STOP_COMMAND and len(words) <= 3:
        return InterruptIntent.STOP
    if len(words) <= _CORRECTION_MAX_WORDS and _CORRECTION_RE.match(normalized):
        # "no thanks" / "no" alone is backing off, not a revision.
        if not re.match(r"^(?:no|nope)(?:\s+(?:thanks|thank\s+you|wait))?$", normalized):
            return InterruptIntent.CORRECTION
    return InterruptIntent.NEW_REQUEST


# A committed final ending on one of these words was cut off mid-thought:
# "I want to check", "compare it to the", "um". Deliberately small; a word
# that often ends a complete request ("it", "now", "them") is not here.
_INCOMPLETE_TRAILING_WORDS = frozenset(
    {
        "to", "the", "a", "an", "and", "or", "but", "of", "for", "with", "about",
        "from", "into", "at", "by", "my", "our", "your", "their", "check",
        "um", "umm", "uh", "er", "erm",
    }
)
_TRAILING_ELLIPSIS_RE = re.compile(r"(?:\.\.\.|\u2026|,|-)\s*$")


def is_syntactically_incomplete(text: str) -> bool:
    """True when a committed final reads as a thought the user has not finished.

    Trailing "..." (or a dangling comma or dash), or a last word that cannot
    end a request (an article, preposition, conjunction, possessive, "check",
    or a hesitation). A question mark always reads as complete.
    """
    stripped = (text or "").strip()
    if not stripped or stripped.endswith("?"):
        return False
    if _TRAILING_ELLIPSIS_RE.search(stripped):
        return True
    words = _WORD_RE.findall(stripped.lower().rstrip(".!"))
    return bool(words) and words[-1] in _INCOMPLETE_TRAILING_WORDS


# A bare go-ahead: the whole utterance says yes and nothing else ("yes",
# "yeah go ahead", "sure, send it", "ok do it now"). Anything more ("yes but
# change the subject", "yes wait") is not bare and is not matched.
_CONFIRM_LEAD = (
    r"(?:yes|yeah|yea|yep|yup|ya|sure|ok|okay|alright|all\s+right|absolutely|definitely|"
    r"correct|right|perfect|great|cool|please|confirm(?:ed)?|approved?)"
)
_CONFIRM_ACT = (
    r"(?:go\s+ahead(?:\s+and\s+(?:send|do|post|create|book|schedule|submit|run)\s+(?:it|that))?|"
    r"(?:send|do|post|create|book|schedule|submit|run|execute|approve|publish|ship)\s+(?:it|that|this)|"
    r"go\s+for\s+it|proceed|please\s+do|let'?s\s+do\s+it|sounds\s+good|"
    r"that\s+works|looks\s+good|that'?s\s+fine|fine)"
)
_BARE_CONFIRMATION_RE = re.compile(
    rf"^(?:{_CONFIRM_LEAD}(?:\s+{_CONFIRM_LEAD})*(?:\s+{_CONFIRM_ACT})?|{_CONFIRM_ACT})"
    r"(?:\s+(?:now|please|right\s+away|thanks|thank\s+you))*$"
)


def is_bare_confirmation(text: str) -> bool:
    """True when the utterance is only a go-ahead: "yes", "yeah go ahead", "send it"."""
    normalized = _normalize(text)
    if not normalized or len(normalized.split()) > 8:
        return False
    return bool(_BARE_CONFIRMATION_RE.match(normalized))
