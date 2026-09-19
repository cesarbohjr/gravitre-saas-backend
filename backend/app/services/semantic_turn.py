"""3.0-C semantic turn kinds — pause vs end vs backchannel vs interrupt.

Deterministic, no LLM on the hot path. Completeness is a heuristic over
transcript shape, not acoustic truth. WRITE targets are never inferred here.
"""
from __future__ import annotations

import re
from enum import Enum

from app.services.pipecat_voice.backchannel_classifier import (
    BackchannelClassification,
    classify_user_utterance,
)

_TRAILING_INCOMPLETE = re.compile(
    r"\b(and|or|but|the|a|an|to|for|with|because|so|if|when|that|of)\s*$",
    re.I,
)
_COMMAND_START = re.compile(
    r"^(show|list|get|send|draft|stop|cancel|open|check|what's|whats|tell)\b",
    re.I,
)
_TERMINAL_PUNCT = re.compile(r"[.?!…][\"')\]]*$")


class SemanticTurnKind(str, Enum):
    PAUSE = "pause"
    END_OF_TURN = "end_of_turn"
    BACKCHANNEL = "backchannel"
    CORRECTION = "correction"
    INTERRUPTION = "interruption"
    CONTINUATION = "continuation"


def looks_incomplete_continuation(text: str) -> bool:
    return bool(_TRAILING_INCOMPLETE.search((text or "").strip()))


def looks_semantically_complete(text: str) -> bool:
    clean = (text or "").strip()
    if not clean:
        return False
    if _TRAILING_INCOMPLETE.search(clean):
        return False
    if _TERMINAL_PUNCT.search(clean):
        return True
    words = clean.split()
    if _COMMAND_START.search(clean) and len(words) >= 3:
        return True
    if len(words) >= 6 and not _TRAILING_INCOMPLETE.search(clean):
        return True
    return False


def looks_like_quick_command(text: str) -> bool:
    clean = (text or "").strip()
    return bool(_COMMAND_START.search(clean) and 2 <= len(clean.split()) <= 10)


def classify_semantic_turn(
    text: str,
    *,
    overlapping_agent: bool,
    pending_finalize: bool,
) -> SemanticTurnKind:
    if overlapping_agent:
        kind = classify_user_utterance(text)
        if kind is BackchannelClassification.BACKCHANNEL:
            return SemanticTurnKind.BACKCHANNEL
        if kind is BackchannelClassification.CORRECTION:
            return SemanticTurnKind.CORRECTION
        if kind is BackchannelClassification.STOP_COMMAND:
            return SemanticTurnKind.INTERRUPTION
        return SemanticTurnKind.INTERRUPTION
    if _TRAILING_INCOMPLETE.search((text or "").strip()):
        return SemanticTurnKind.CONTINUATION
    if pending_finalize and looks_semantically_complete(text):
        return SemanticTurnKind.END_OF_TURN
    if pending_finalize:
        return SemanticTurnKind.PAUSE
    return SemanticTurnKind.PAUSE
