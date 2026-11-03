"""Resolve narrow inventory follow-ups without rewriting action requests."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConnectorInventoryIntent:
    category: str | None = None


_INVENTORY = re.compile(
    r"(?i)^(?:(?:ok(?:ay)?|k)[,.]?\s+)?(?:can you (?:please )?(?:tell me|show me)\s+)?"
    r"(?:what|which)\s+(?:other\s+)?(?P<email>e-?mail\s+)?(?:connectors?|integrations?|services?|accounts?)\s+"
    r"(?:do (?:i|we) have(?: (?:connected|configured|installed))?|are (?:connected|configured|installed)(?: (?:here|for me|in (?:my|this) workspace))?)"
    r"[?.!]*$"
)
_EMAIL_LIST = re.compile(
    r"(?i)^(?:please\s+)?(?:list|show|check)\s+(?:me\s+)?(?:my|our|the)\s+(?:connected\s+)?e-?mail\s+(?:connectors?|integrations?|services?|accounts?)[?.!]*$"
)
_FOLLOW_UP = re.compile(
    r"(?i)^(?:(?:ok(?:ay)?|k)[,.]?\s+)?(?:do (?:i|we) not have (?:any )?others|"
    r"(?:are|aren't) there (?:any )?others|what (?:about )?(?:the )?(?:other ones|others)|"
    r"which ones|list them(?: again)?|show (?:me )?the others)[?.!]*$"
)
_EMAIL_FOLLOW_UP = re.compile(r"(?i)^(?:what|which) other e-?mails? do (?:i|we) have[?.!]*$")


def _utterance(message: str) -> str:
    text = " ".join((message or "").split())
    text = re.sub(r"(?i)^(?:ok(?:ay)?[,.]?\s+)?i asked(?: asked)?\s+", "", text)
    return re.sub(r"(?i)^what other gmails[.…]+\s*", "", text)


def is_inventory_followup(message: str) -> bool:
    text = _utterance(message)
    return bool(_FOLLOW_UP.fullmatch(text) or _EMAIL_FOLLOW_UP.fullmatch(text))


def connector_inventory_intent(message: str, history: list[dict[str, Any]] | None = None) -> ConnectorInventoryIntent | None:
    text = _utterance(message)
    match = _INVENTORY.fullmatch(text)
    if match:
        # Generic services/accounts could mean business records; require email.
        if not match.group("email") and not re.search(r"(?i)\b(connectors?|integrations?)\b", text):
            return None
        return ConnectorInventoryIntent(category="email" if match.group("email") else None)
    if _EMAIL_LIST.fullmatch(text):
        return ConnectorInventoryIntent(category="email")
    if not (_FOLLOW_UP.fullmatch(text) or _EMAIL_FOLLOW_UP.fullmatch(text)):
        return None
    # Only the most recent user subject can anchor a follow-up. An unrelated
    # question or topic change must not resurrect an earlier connector topic.
    previous = [row for row in (history or [])[-12:] if isinstance(row, dict) and row.get("role") == "user"]
    for row in reversed(previous[-4:]):
        content = row.get("content")
        if not isinstance(content, str):
            return None
        prior = connector_inventory_intent(content)
        if prior is not None:
            return prior
        if not is_inventory_followup(content):
            return None
    return None
