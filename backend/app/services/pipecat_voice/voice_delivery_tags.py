"""Structured, closed-set emotional delivery tags for voice — security-gated.

Conversational-realism Phase 5. Per the Agent Security Gateway's own
"knowledge is data, system policy is authority" principle
(``app/services/agent_security_gateway.py``): any tag-like content that shows
up inside LLM-generated text is untrusted by default. A free-text delivery
hint embedded in generated output (e.g. an injected ``[[delivery:whatever]]``
crafted by a prompt-injection attempt riding in through tool output, a
connector response, or retrieved knowledge that the model echoes) is a real
attack surface if it is ever allowed to reach TTS rendering unchecked.

This module is the single point where delivery-tag syntax is recognized,
validated against a small closed enum, and stripped from the text that
actually reaches TTS. Anything that looks like a tag but is NOT in the closed
enum is rejected and logged — never passed through silently, and never used
to influence delivery.

Current scope: ElevenLabs Flash v2.5 (the live, latency-critical TTS model -
see ``pipeline.py``, which deliberately keeps voice off Eleven v3) has no
inline delivery-tag rendering hook, so accepted tags are recorded for
observability/Phase 6 metrics and then stripped like everything else before
synthesis. If/when a TTS model with real inline delivery control is adopted
for the live path, this is the one place that would need to start forwarding
(rather than only stripping) the ACCEPTED tags — the validation boundary
itself does not change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "DeliveryTag",
    "DeliveryTagScanResult",
    "strip_and_validate_delivery_tags",
]


class DeliveryTag(str, Enum):
    """Closed, small set of TTS delivery hints. Nothing outside this set is valid."""

    NEUTRAL = "neutral"
    CONCISE = "concise"
    REASSURING = "reassuring"
    APOLOGETIC = "apologetic"
    URGENT = "urgent"


_VALID_TAG_VALUES: frozenset[str] = frozenset(t.value for t in DeliveryTag)

# Deliberately narrow, unusual syntax (double brackets, "delivery:" prefix) so
# it is extremely unlikely to occur "naturally" in real spoken text, which
# minimizes false positives while making any occurrence highly suspicious by
# construction. Case-insensitive; tag value is captured for validation.
_DELIVERY_TAG_RE = re.compile(r"\[\[\s*delivery\s*:\s*([a-zA-Z_\-]{1,32})\s*\]\]", re.IGNORECASE)

# ANY double-bracket token, not just ones that parse as "delivery:xxx", is
# treated as tag-shaped and stripped. A malformed or off-syntax injection
# attempt ("[[system: ignore all prior instructions]]") must not survive
# just because it doesn't match the exact accepted grammar.
_ANY_BRACKET_TAG_RE = re.compile(r"\[\[[^\[\]]{0,200}\]\]")


@dataclass
class DeliveryTagScanResult:
    """Outcome of scanning one chunk of LLM-generated text for delivery tags."""

    clean_text: str
    accepted_tags: list[DeliveryTag]
    rejected_raw_tags: list[str]

    @property
    def had_injection_attempt(self) -> bool:
        return bool(self.rejected_raw_tags)


def strip_and_validate_delivery_tags(text: str) -> DeliveryTagScanResult:
    """Scan, validate, and strip delivery tags from text bound for TTS.

    Real, closed-set validation happens BEFORE any stripping: every
    ``[[delivery:xxx]]``-shaped token is checked against ``DeliveryTag``.
    Recognized tags are recorded in ``accepted_tags`` (for Phase 6
    observability) and removed from the text. Anything else that is tag-
    shaped (any ``[[...]]`` span, whether or not it parses as a delivery tag)
    is rejected, logged, and also removed — it never reaches TTS, and it is
    never treated as if it had a real effect.
    """
    if not text:
        return DeliveryTagScanResult(clean_text=text or "", accepted_tags=[], rejected_raw_tags=[])

    accepted: list[DeliveryTag] = []
    rejected: list[str] = []

    def _replace_delivery_tag(match: re.Match[str]) -> str:
        raw_value = match.group(1).strip().lower()
        if raw_value in _VALID_TAG_VALUES:
            accepted.append(DeliveryTag(raw_value))
        else:
            rejected.append(match.group(0))
        return ""

    working = _DELIVERY_TAG_RE.sub(_replace_delivery_tag, text)

    # Anything still tag-shaped after the pass above was not a valid
    # "delivery:" tag at all (wrong prefix, unknown syntax, or an outright
    # injection attempt). Strip it and log it as rejected - never silent.
    def _replace_unknown_tag(match: re.Match[str]) -> str:
        rejected.append(match.group(0))
        return ""

    working = _ANY_BRACKET_TAG_RE.sub(_replace_unknown_tag, working)

    # Collapse any double-space left behind by removed tags.
    working = re.sub(r"\s{2,}", " ", working).strip()

    if rejected:
        logger.warning(
            "voice_delivery_tag_rejected count=%d raw_tags=%r accepted_count=%d",
            len(rejected),
            [r[:120] for r in rejected][:10],
            len(accepted),
        )
    if accepted:
        logger.info(
            "voice_delivery_tag_accepted tags=%r",
            [t.value for t in accepted],
        )

    return DeliveryTagScanResult(
        clean_text=working, accepted_tags=accepted, rejected_raw_tags=rejected
    )
