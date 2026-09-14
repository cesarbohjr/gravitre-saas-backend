"""Ground unified-turn LIVE replies in org connector inventory.

Prevents false "X isn't Connected" claims when ``list_connected_integrations``
already shows the vendor as connected for this org.
"""
from __future__ import annotations

import re

from app.services.connector_semantic_registry import integration_slug_for_label

_DISCONNECT_CLAIM_RE = re.compile(
    r"(?i)\b(?P<label>[\w\s]+?)\s+(?:isn't|is\s+not|not)\s+connected\b"
)
_DISCONNECT_HERE_RE = re.compile(
    r"(?i)\b(?P<label>[\w\s]+?)\s+(?:isn't|is\s+not|not)\s+connected\s+here\b"
)


def _integration_slug_for_label(label: str) -> str | None:
    return integration_slug_for_label(label)


def integrations_claimed_disconnected(message: str) -> list[str]:
    """Return integration slugs the assistant text claims are not connected."""
    text = message or ""
    labels: list[str] = []
    for pattern in (_DISCONNECT_HERE_RE, _DISCONNECT_CLAIM_RE):
        for match in pattern.finditer(text):
            label = str(match.group("label") or "").strip()
            if label:
                labels.append(label)
    slugs: list[str] = []
    for label in labels:
        slug = _integration_slug_for_label(label)
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs


def unified_live_message_claims_false_disconnect(
    message: str,
    connected_integrations: list[str] | None,
) -> bool:
    """True when reply claims a vendor is disconnected but org inventory says connected."""
    connected = {str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()}
    if not connected:
        return False
    for slug in integrations_claimed_disconnected(message):
        if slug in connected:
            return True
    return False
