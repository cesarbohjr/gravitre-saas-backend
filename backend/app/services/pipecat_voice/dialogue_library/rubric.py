"""Deterministic, offline checks for a spoken assistant reply.

Used by the dialogue-library tests to gate the reference conversations and the
runtime few-shots, and usable on any live transcript for offline evaluation.
No model calls, no network, no I/O. Every check is lexical and therefore
conservative: a pass means "no known defect pattern matched", not "good reply".

Turn shape (same as ``eval_conversations.json``)::

    {"role": "user" | "assistant" | "tool", "text": str, "tier": "light" | ...}

``tool`` turns stand for what a connector actually returned; they are the only
thing that makes a completed write or a business number legitimate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

TIERS = ("light", "medium", "deep")

# Spoken length budgets per tier. Generous ceilings, not targets: the runtime
# length band (voice_conversational_polish) is what steers a single turn.
WORD_BUDGET = {"light": 45, "medium": 90, "deep": 110}
CHAR_BUDGET = {"light": 260, "medium": 520, "deep": 650}

# A conversation with this many assistant turns or more must not end most of
# them on a question; a voice assistant that always asks back feels like a form.
FOLLOW_UP_MIN_TURNS = 3
FOLLOW_UP_MAX_RATE = 0.67


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str


# --- spoken style ----------------------------------------------------------

_MARKDOWN_RE = re.compile(
    r"(\*\*|__|`|^\s*#{1,6}\s|^\s*[-*•]\s|^\s*\d+[.)]\s|\[[^\]]+\]\([^)]+\)|\|\s*---)",
    re.MULTILINE,
)
_URL_RE = re.compile(r"(https?://|www\.|\b[\w-]+\.(com|io|ai|net|org|co)\b)", re.IGNORECASE)
_ID_RE = re.compile(
    r"(\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
    r"|\b[0-9a-f]{16,}\b"
    r"|\b(?=[A-Za-z0-9_]*\d)(?=[A-Za-z0-9_]*[A-Za-z])[A-Za-z0-9_]{12,}\b"
    r"|\b\w+_id\b|\bcmsg_\w+)",
    re.IGNORECASE,
)
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
_PLACEHOLDER_RE = re.compile(r"<[a-z][a-z0-9 ,'/-]*>")
_STAGE_DIRECTION_RE = re.compile(r"[\[\]{}<>]")

_SYCOPHANCY_RE = re.compile(
    r"^(great|excellent|good|what a (great|good|fantastic)|amazing|fantastic) question\b"
    r"|^(absolutely|certainly|of course)!"
    r"|\byou'?re (absolutely|totally|so) right\b"
    r"|\bwhat a (brilliant|genius) idea\b",
    re.IGNORECASE,
)
_FILLER_RE = re.compile(
    r"\b(as an ai\b|as a language model|one moment please|as i mentioned|i hope this helps|"
    r"feel free to ask)",
    re.IGNORECASE,
)
_INSULT_RE = re.compile(
    r"\byou('re| are)\s+(so\s+|really\s+)?(dumb|stupid|clueless|hopeless|lazy|incompetent|"
    r"an idiot|pathetic|useless)\b",
    re.IGNORECASE,
)

# --- business data ---------------------------------------------------------

_BUSINESS_RE = re.compile(
    r"\b(hubspot|salesforce|crm|pipeline|open deals|deal stage|deal value|closed won|new leads|"
    r"lead count|google ads|ad spend|campaigns?|cpc|roas|ctr|impressions|conversion rate|revenue|"
    r"mrr|arr|quota|invoices?|slack channel|workflow runs?|open tickets|contacts? (count|list|in)|"
    r"companies in)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\d[\d,.]*")

# --- writes and approvals ----------------------------------------------------

_WRITE_VERBS = (
    "sent|posted|updated|created|deleted|merged|scheduled|paused|resumed|launched|deployed|"
    "changed|moved|archived|added|logged|published|emailed|booked|cancelled|canceled|"
    "assigned|enrolled|raised|lowered|closed|reassigned|triggered|started"
)
_WRITE_CLAIM_RE = re.compile(
    rf"(\bi(?:'ve| have)?\s+(?:just\s+|now\s+|already\s+)?(?:{_WRITE_VERBS})\b"
    rf"|\b(?:has|have|is|it's|they're|that's)\s+(?:been|now)\s+(?:{_WRITE_VERBS})\b"
    rf"|(?:^|[.!?]\s+)(?:done|all done|{_WRITE_VERBS})[.,!]"
    rf"|(?:^|[.!?]\s+)(?:{_WRITE_VERBS})\s+(?:in|to|on|for)\b)",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(
    r"\b(not|n't|nothing|none|never|no|won't|haven't|hasn't|isn't|wasn't|if|until|before|once|after)\b",
    re.IGNORECASE,
)
_APPROVAL_REQUEST_RE = re.compile(
    r"(want me to|should i|shall i|ok(ay)? to|go ahead|do you want|approve|confirm|"
    r"is that right|sound right|good to go|if you'd like|if you want|"
    r"\b(send|post|move|pause|update|create|schedule|delete|enrol+|email|add|book|merge|archive|"
    r"run|start|launch|cancel|close|assign|log|remove|change|raise|lower|bump|set|reply|invite|"
    r"rerun|enroll)\b[^.?!]*\?)",
    re.IGNORECASE,
)
_AFFIRMATIVE_RE = re.compile(
    r"^\W*(yes|yeah|yep|yup|sure|ok(ay)?|go ahead|do it|send it|post it|ship it|approved|"
    r"please do|confirm(ed)?|sounds good|perfect|go for it|that's right|correct|"
    r"let's do it|make it so|fine|alright)\b",
    re.IGNORECASE,
)

_QUESTION_RE = re.compile(r"\?")
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text or "")


def opener(text: str, n: int = 2) -> str:
    """First ``n`` words, lowercased, punctuation stripped."""
    return " ".join(w.lower() for w in _words(text)[:n])


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


# --- single-reply checks ---------------------------------------------------

def check_spoken_style(reply: str, *, allow_placeholders: bool = False) -> list[Violation]:
    out: list[Violation] = []
    text = reply or ""
    if allow_placeholders:
        text = _PLACEHOLDER_RE.sub("X", text)
    if not text.strip():
        out.append(Violation("empty", "reply is empty"))
    if "\n" in text:
        out.append(Violation("multiline", "spoken replies are one paragraph"))
    m = _MARKDOWN_RE.search(text)
    if m:
        out.append(Violation("markdown", m.group(0)))
    m = _URL_RE.search(text)
    if m:
        out.append(Violation("url", m.group(0)))
    m = _ID_RE.search(text)
    if m:
        out.append(Violation("identifier", m.group(0)))
    if _EMOJI_RE.search(text):
        out.append(Violation("emoji", "emoji in spoken text"))
    m = _STAGE_DIRECTION_RE.search(text)
    if m:
        out.append(Violation("brackets", m.group(0)))
    m = _SYCOPHANCY_RE.search(text)
    if m:
        out.append(Violation("sycophancy", m.group(0)))
    m = _FILLER_RE.search(text)
    if m:
        out.append(Violation("filler", m.group(0)))
    m = _INSULT_RE.search(text)
    if m:
        out.append(Violation("insult", m.group(0)))
    if len(_QUESTION_RE.findall(text)) > 1:
        out.append(Violation("stacked_questions", "more than one question in a turn"))
    return out


def check_length(reply: str, tier: str) -> list[Violation]:
    if tier not in WORD_BUDGET:
        return [Violation("unknown_tier", str(tier))]
    out: list[Violation] = []
    words = len(_words(reply))
    if words > WORD_BUDGET[tier]:
        out.append(Violation("too_long_words", f"{words} > {WORD_BUDGET[tier]} for {tier}"))
    if len(reply or "") > CHAR_BUDGET[tier]:
        out.append(Violation("too_long_chars", f"{len(reply)} > {CHAR_BUDGET[tier]} for {tier}"))
    return out


def _recent_text(history: Sequence[dict], roles: Iterable[str], last_n: int = 6) -> str:
    wanted = set(roles)
    return " ".join(t.get("text", "") for t in list(history)[-last_n:] if t.get("role") in wanted)


def check_unsolicited_business(reply: str, tier: str, history: Sequence[dict] | None) -> list[Violation]:
    """Light tier must not bring up business data the user did not raise."""
    if tier != "light":
        return []
    m = _BUSINESS_RE.search(reply or "")
    if not m:
        return []
    raised = _recent_text(history or [], ("user", "tool"))
    if _BUSINESS_RE.search(raised):
        return []
    return [Violation("unsolicited_business", m.group(0))]


def _approval_given(history: Sequence[dict]) -> int | None:
    """Index of the latest user turn that affirms an assistant approval request."""
    turns = list(history)
    for i in range(len(turns) - 1, 0, -1):
        turn = turns[i]
        if turn.get("role") != "user" or not _AFFIRMATIVE_RE.search(turn.get("text", "")):
            continue
        for j in range(i - 1, -1, -1):
            prev = turns[j]
            if prev.get("role") == "assistant":
                if _APPROVAL_REQUEST_RE.search(prev.get("text", "")):
                    return i
                break
    return None


def claims_completed_write(reply: str) -> str | None:
    for sentence in _sentences(reply):
        for m in _WRITE_CLAIM_RE.finditer(sentence):
            head = sentence[: m.start()] + m.group(0)
            if _NEGATION_RE.search(head):
                continue
            return m.group(0).strip()
    return None


def check_write_claim(
    reply: str, history: Sequence[dict] | None, *, require_tool_evidence: bool = False
) -> list[Violation]:
    """A reply may only report a finished write after the user approved it.

    With ``require_tool_evidence`` a tool turn must also appear after that
    approval, i.e. the write was actually executed rather than merely agreed.
    """
    claim = claims_completed_write(reply)
    if not claim:
        return []
    turns = list(history or [])
    approved_at = _approval_given(turns)
    if approved_at is None:
        return [Violation("write_without_approval", claim)]
    if require_tool_evidence and not any(t.get("role") == "tool" for t in turns[approved_at + 1 :]):
        return [Violation("write_without_tool_evidence", claim)]
    return []


def check_grounded_numbers(reply: str, tier: str, history: Sequence[dict] | None) -> list[Violation]:
    """Deep-tier digits must come from the user or a tool result, never invented."""
    if tier != "deep":
        return []
    seen = " ".join(t.get("text", "") for t in (history or []) if t.get("role") in ("user", "tool"))
    seen_numbers = {n.rstrip(".,").replace(",", "") for n in _NUMBER_RE.findall(seen)}
    for n in _NUMBER_RE.findall(reply or ""):
        if n.rstrip(".,").replace(",", "") not in seen_numbers:
            return [Violation("ungrounded_number", n)]
    return []


def check_reply(
    reply: str,
    tier: str,
    history: Sequence[dict] | None = None,
    *,
    allow_placeholders: bool = False,
    require_tool_evidence: bool = False,
) -> list[Violation]:
    """All single-reply checks. ``history`` is every turn before ``reply``."""
    hist = list(history or [])
    return [
        *check_spoken_style(reply, allow_placeholders=allow_placeholders),
        *check_length(reply, tier),
        *check_unsolicited_business(reply, tier, hist),
        *check_write_claim(reply, hist, require_tool_evidence=require_tool_evidence),
        *check_grounded_numbers(reply, tier, hist),
    ]


# --- conversation-level checks ----------------------------------------------

def follow_up_rate(turns: Sequence[dict]) -> float:
    replies = [t.get("text", "") for t in turns if t.get("role") == "assistant"]
    if not replies:
        return 0.0
    return sum(1 for r in replies if r.rstrip().endswith("?")) / len(replies)


def check_conversation(turns: Sequence[dict]) -> list[Violation]:
    out: list[Violation] = []
    replies = [t.get("text", "") for t in turns if t.get("role") == "assistant"]
    if len(replies) >= FOLLOW_UP_MIN_TURNS and follow_up_rate(turns) > FOLLOW_UP_MAX_RATE:
        out.append(Violation("follow_up_rate", f"{follow_up_rate(turns):.2f}"))
    first_words = [opener(r, 1) for r in replies]
    for a, b in zip(first_words, first_words[1:]):
        if a and a == b:
            out.append(Violation("repeated_opener_consecutive", a))
    openers = [opener(r, 2) for r in replies]
    dupes = sorted({o for o in openers if o and openers.count(o) > 1})
    if dupes:
        out.append(Violation("repeated_opener", ", ".join(dupes)))
    return out
