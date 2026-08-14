"""Marketing-intent helpers — honest catalog gaps instead of silent substitutions."""
from __future__ import annotations

import re

from app.connectors.action_catalog.registry import get_vendor_spec

HUBSPOT_MENTION = re.compile(r"\bhubspot\b", re.I)
EMAIL_CAMPAIGN_INTENT = re.compile(
    r"\b(?:email\s+)?campaign(?:s)?\b|\bmarketing\s+email\b|\bnewsletter\b",
    re.I,
)


def _hubspot_has_email_campaign_create() -> bool:
    spec = get_vendor_spec("hubspot")
    if spec is None:
        return False
    for action in spec.all_actions():
        action_id = str(action.id or "").lower()
        if "campaign" in action_id and action_id.endswith(".create"):
            return True
    return False


def hubspot_email_campaign_catalog_gap(message: str) -> str | None:
    """Return an honest operator message when HubSpot email campaign create is unavailable."""
    text = (message or "").strip()
    if not text or not HUBSPOT_MENTION.search(text) or not EMAIL_CAMPAIGN_INTENT.search(text):
        return None
    if _hubspot_has_email_campaign_create():
        return None
    return (
        "HubSpot **email campaign creation** is not available in the connected action catalog yet. "
        "I won't substitute **Create contact** or another unrelated write.\n\n"
        "Connected HubSpot writes today include contacts, deals, and static lists. "
        "If you want a static list named **outreach**, say so explicitly; "
        "for broadcast/email campaigns we need a catalog action before I can propose one."
    )
