"""Curated voice dialogue library.

Only ``runtime_fewshots.json`` is used at runtime, through :func:`select_fewshots`.
``eval_conversations.json`` is an offline evaluation set gated by ``rubric.py``.
Nothing in this package is training or fine-tuning data (see README.md).
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_DIR = Path(__file__).resolve().parent
RUNTIME_FEWSHOTS_PATH = _DIR / "runtime_fewshots.json"
EVAL_CONVERSATIONS_PATH = _DIR / "eval_conversations.json"

HEADER = "Style examples (do not repeat verbatim; match tone, not content):"
MAX_BLOCK_CHARS = 700
DEEP_MAX_EXAMPLES = 1

_TOKEN_RE = re.compile(r"[a-z0-9']+")
_STOPWORDS = frozenset(
    "a an the and or but to of in on for at by with is are was were be been it its it's this that "
    "i i'm i've me my we our you your he she they them do does did can could would should will just "
    "so if as from about what what's how is there here actually really like get got you're im".split()
)

# Lexical cues in the user's message that suggest a trait. Substring matches
# against the lowercased message; deliberately small and cheap.
_TRAIT_CUES: dict[str, tuple[str, ...]] = {
    "humor": ("joke", "funny", "lol", "haha", "pun", "laugh"),
    "banter": ("you're funny", "you're actually", "do you ever", "favorite"),
    "sarcasm": ("fantastic, another", "great, another", "love sitting", "best hobby", "oh great", "oh fantastic"),
    "empathy": ("tired", "exhausted", "stressed", "sad", "rough", "awful", "upset", "laid off",
                "sorry", " vet", "died", "sick", "anxious", "long day"),
    "sarcasm_withheld": ("laid off", "died", " vet", "lost", "funeral", "hospital"),
    "hesitation": (" um ", " um,", " uh ", " uh,", "hmm", "lost my train"),
    "self-correction": ("scratch that", "actually", "never mind", "i mean", "no wait"),
    "interruption": ("wait,", "hold on", "sorry, ", "seriously?"),
    "clarification": ("which one", "what do you mean", "better at it", "simpler"),
    "explanation": ("why", "how does", "how do", "explain", "what is", "what's the difference"),
    "comparison": (" or ", " vs", "versus", "which is better", "compare"),
    "brainstorming": ("ideas", "brainstorm", "name for", "suggest", "think of"),
    "disagreement": ("right?", "agree", "always", "isn't it", "great idea"),
    "business_read": ("pipeline", "deals", "leads", "hubspot", "campaign", " ads", "how many", "report",
                      "conversions", "revenue", "quota"),
    "approval_write": ("send", "post", "email", "update", "pause", "move", "delete", "schedule",
                       "create", "book", "enroll"),
    "progress": ("how's it going", "status", "done yet", "progress"),
    "tool_failure": ("slack", "connected", "not working"),
}
_AFFIRMATIVE_RE = re.compile(r"^\W*(yes|yeah|yep|sure|ok(ay)?|go ahead|do it|send it|please do)\b")


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}


@lru_cache(maxsize=1)
def _load_runtime() -> dict[str, tuple[tuple[str, frozenset[str], frozenset[str], str], ...]]:
    """Per tier: (rendered exchange, traits, lexical tokens, assistant text) tuples."""
    raw = json.loads(RUNTIME_FEWSHOTS_PATH.read_text(encoding="utf-8"))
    out: dict[str, tuple[tuple[str, frozenset[str], frozenset[str], str], ...]] = {}
    for tier, examples in raw.get("tiers", {}).items():
        rows = []
        for ex in examples:
            turns = ex.get("turns") or []
            rendered = "\n".join(
                f"{'User' if t['role'] == 'user' else 'Assistant'}: {t['text']}" for t in turns
            )
            user_text = " ".join(t["text"] for t in turns if t["role"] == "user")
            assistant_text = " ".join(t["text"] for t in turns if t["role"] == "assistant")
            lexical = frozenset(_tokens(user_text) | {k.lower() for k in ex.get("keywords", [])})
            rows.append((rendered, frozenset(ex.get("traits", [])), lexical, assistant_text))
        out[tier] = tuple(rows)
    return out


def _message_traits(message: str, history: list[dict] | None) -> set[str]:
    lowered = f" {message.lower()} "
    traits = {trait for trait, cues in _TRAIT_CUES.items() if any(c in lowered for c in cues)}
    if history and _AFFIRMATIVE_RE.search(message.lower()):
        last_assistant = next(
            (t.get("text", "") for t in reversed(history) if t.get("role") == "assistant"), ""
        )
        if last_assistant.rstrip().endswith("?"):
            traits |= {"approval_write", "confirmation"}
    return traits


def select_fewshots(
    tier: str, message: str, history: list[dict] | None = None, k: int = 2
) -> str:
    """Pick up to ``k`` style exchanges for ``tier`` that best match ``message``.

    Deterministic lexical scoring (trait cues plus token overlap, ties broken by
    file order). Only matching examples are used; with no match, the tier's
    first example stands in. Examples whose assistant lines already appear in
    ``history`` are skipped. Returns "" for an unknown tier, ``k < 1`` or any error.
    """
    try:
        rows = _load_runtime().get(tier)
        if not rows or k < 1:
            return ""
        if tier == "deep":
            k = min(k, DEEP_MAX_EXAMPLES)
        text = message or ""
        msg_tokens = _tokens(text)
        msg_traits = _message_traits(text, history)
        seen = " ".join(t.get("text", "") for t in (history or []) if t.get("role") == "assistant")
        scored = []
        for index, (rendered, traits, lexical, assistant_text) in enumerate(rows):
            if seen and assistant_text and assistant_text in seen:
                continue
            score = 3 * len(traits & msg_traits) + len(lexical & msg_tokens)
            scored.append((-score, index, rendered))
        scored.sort()
        # Only examples that actually match; with no match at all, fall back to
        # the tier's first (most neutral) example rather than a random tone.
        matched = [row for row in scored if row[0] < 0]
        if not matched:
            matched = sorted(scored, key=lambda row: row[1])[:1]
        block = HEADER
        added = 0
        for _, _, rendered in matched:
            if added >= k:
                break
            candidate = f"{block}\n\n{rendered}"
            if len(candidate) > MAX_BLOCK_CHARS:
                continue
            block = candidate
            added += 1
        return block if added else ""
    except Exception:  # never let style examples break a voice turn
        logger.warning("dialogue_library.select_fewshots_failed", exc_info=True)
        return ""


__all__ = ["select_fewshots", "RUNTIME_FEWSHOTS_PATH", "EVAL_CONVERSATIONS_PATH", "HEADER"]
