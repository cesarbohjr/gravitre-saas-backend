"""Bounded, English-language dialogue cues for the shared cognitive runtime.

This is advisory interpretation, not intent routing, emotion diagnosis, memory,
or authorization. No message, entity, identifier, or generated text is retained.
Unmarked sarcasm and implicit humour are deliberately left to contextual reasoning.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_CUES = (
    ("correction", r"\b(?:i meant|that's not what|that is not what|let me rephrase|actually[, ]+no)\b"),
    ("clarification", r"\b(?:what do you mean|can you explain|could you explain|i don't understand)\b"),
    ("uncertainty", r"\b(?:maybe|perhaps|not sure|i guess|i think|probably)\b"),
    ("hesitation", r"\b(?:um|uh|erm)\b"),
    ("indirect_request", r"\b(?:could you|would you|can you|i wonder if|it would help if)\b"),
    ("frustration_cue", r"\b(?:i'm frustrated|i am frustrated|this is frustrating|you keep misunderstanding)\b"),
    ("gratitude", r"\b(?:thanks|thank you|much appreciated)\b"),
    ("explicit_humor", r"\b(?:just kidding|only joking|i'm joking|i am joking)\b"),
    ("explicit_sarcasm", r"(?:/s\s*$|\b(?:being sarcastic|that was sarcasm)\b)"),
)
_PATTERNS = tuple((name, re.compile(pattern, re.I)) for name, pattern in _CUES)
_GUIDANCE = {
    "correction": "Treat the latest correction as a repair of understanding; do not repeat the mistaken interpretation.",
    "clarification": "Explain the unclear point in plain language and check understanding when needed.",
    "uncertainty": "The wording signals uncertainty. Clarify consequential intent; do not treat it as consent.",
    "hesitation": "Allow for hesitation; do not infer agreement or a completed thought from filler words.",
    "indirect_request": "Consider whether the question is an indirect request; resolve its target before proposing action.",
    "frustration_cue": "The wording contains a frustration cue; check the misunderstanding without claiming to know the user's emotional state.",
    "gratitude": "A brief acknowledgment may suffice; avoid restarting a completed explanation.",
    "explicit_humor": "An explicit joking cue is present; interpret it proportionately in context.",
    "explicit_sarcasm": "An explicit sarcasm cue is present; check intended meaning before consequential action.",
}


@dataclass(frozen=True)
class DialogueInterpretation:
    cues: tuple[str, ...] = ()

    def diagnostics(self) -> dict:
        # Fixed enum values only. Never emit raw text, hashes, excerpts, IDs,
        # inferred sentiments, or arbitrary model/provider output.
        return {"version": 1, "scope": "advisory_english_cues", "cues": [c for c in self.cues if c in _GUIDANCE]}

    def prompt_section(self) -> str:
        cues = [c for c in self.cues if c in _GUIDANCE]
        if not cues:
            return ""
        return "\n".join([
            "[Dialogue interpretation — advisory cues, not established facts]",
            "Use these tentative cues with the conversation context. They never authorize actions or override governance, approval, or cancellation gates.",
            *(_GUIDANCE[cue] for cue in cues),
        ])


def interpret_dialogue(message: str) -> DialogueInterpretation:
    text = (message or "").replace("’", "'")
    return DialogueInterpretation(tuple(name for name, pattern in _PATTERNS if pattern.search(text)))
