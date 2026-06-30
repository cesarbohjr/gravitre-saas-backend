"""Live chunk conflict detection for response-time context building."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

_NEGATION_PAIRS: tuple[tuple[str, str], ...] = (
    ("yes", "no"),
    ("true", "false"),
    ("enabled", "disabled"),
    ("active", "inactive"),
    ("increase", "decrease"),
    ("approved", "rejected"),
    ("allow", "deny"),
    ("success", "failure"),
    ("open", "closed"),
)

_TOKEN = re.compile(r"\w+")


def _normalize_text(value: str) -> str:
    return " ".join(_TOKEN.findall((value or "").lower()))


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _has_opposing_sentiment(a: str, b: str) -> bool:
    tokens_a = set(_TOKEN.findall(a.lower()))
    tokens_b = set(_TOKEN.findall(b.lower()))
    for left, right in _NEGATION_PAIRS:
        if (left in tokens_a and right in tokens_b) or (right in tokens_a and left in tokens_b):
            return True
    return False


def dedupe_chunks(chunks: list[dict[str, Any]], *, similarity_threshold: float = 0.92) -> list[dict[str, Any]]:
    """Drop near-duplicate chunks while preserving highest score first."""
    ordered = sorted(chunks, key=lambda row: float(row.get("score") or 0.0), reverse=True)
    kept: list[dict[str, Any]] = []
    for candidate in ordered:
        content = _normalize_text(str(candidate.get("content") or candidate.get("snippet") or ""))
        if not content:
            continue
        if any(_similarity(content, _normalize_text(str(row.get("content") or row.get("snippet") or ""))) >= similarity_threshold for row in kept):
            continue
        kept.append(candidate)
    return kept


def detect_chunk_conflicts(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Lightweight heuristic conflict detection (no LLM).
    Returns conflicting chunk pairs with a short reason.
    """
    conflicts: list[dict[str, Any]] = []
    for index, left in enumerate(chunks):
        left_text = str(left.get("content") or left.get("snippet") or "")
        left_norm = _normalize_text(left_text)
        if not left_norm:
            continue
        for right in chunks[index + 1 :]:
            right_text = str(right.get("content") or right.get("snippet") or "")
            right_norm = _normalize_text(right_text)
            if not right_norm:
                continue
            sim = _similarity(left_norm, right_norm)
            if sim < 0.35:
                continue
            if _has_opposing_sentiment(left_text, right_text):
                conflicts.append(
                    {
                        "chunk_a_id": left.get("id") or left.get("chunk_id"),
                        "chunk_b_id": right.get("id") or right.get("chunk_id"),
                        "source_a": left.get("source") or left.get("title"),
                        "source_b": right.get("source") or right.get("title"),
                        "reason": "Similar topic with opposing statements",
                        "similarity": round(sim, 3),
                    }
                )
    return conflicts


def format_conflicts_for_prompt(conflicts: list[dict[str, Any]]) -> str:
    if not conflicts:
        return ""
    lines = ["Potential conflicting sources detected:"]
    for item in conflicts[:5]:
        lines.append(
            f"- {item.get('source_a') or 'Source A'} vs {item.get('source_b') or 'Source B'}: "
            f"{item.get('reason') or 'possible disagreement'}"
        )
    return "\n".join(lines)
