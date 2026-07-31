"""Classify connector write effects so no-op / idempotent finds are not sold as creates.

Class-level guard for false COMPLETED claims (e.g. Apollo label already exists →
"Found existing MSP Prospects" marked created_record + completed with 0 steps).
"""
from __future__ import annotations

import re
from typing import Any

# Multi-vendor enrich/sync language that must not collapse to single-list create.
_ENRICH_OR_SYNC = re.compile(
    r"\b("
    r"enrich(?:ment|ed|ing)?"
    r"|clay"
    r"|sync(?:ed|ing)?"
    r"|then\s+add"
    r"|add\s+those"
    r"|static\s+list"
    r"|hubspot\s+(?:static\s+)?list"
    r")\b",
    re.IGNORECASE,
)


def is_already_existed_effect(result_data: dict[str, Any] | None) -> bool:
    """True when vendor returned an idempotent find (no net-new create)."""
    if not isinstance(result_data, dict):
        return False
    if result_data.get("already_existed") is True:
        return True
    nested = result_data.get("label") if isinstance(result_data.get("label"), dict) else None
    if isinstance(nested, dict) and nested.get("already_existed") is True:
        return True
    return False


def is_multi_system_enrich_or_sync_intent(message: str) -> bool:
    """True when NL asks for list work spanning ≥2 of Apollo/Clay/HubSpot with enrich/sync.

    Prevents LIST_CREATE_INTENT from suppressing orchestration for prompts like:
    Use Clay to enrich Apollo list \"MSP Prospects\", then add to HubSpot static list \"MSPs\".
    """
    text = (message or "").strip().lower()
    if not text:
        return False
    vendors = sum(1 for v in ("apollo", "clay", "hubspot") if v in text)
    if vendors < 2:
        return False
    return bool(_ENRICH_OR_SYNC.search(text))


def prefers_single_list_create(message: str) -> bool:
    """STA-305 omit-name list create prefers governed connector — unless multi-system enrich."""
    from app.services.chat_connector_models import LIST_CREATE_INTENT

    if not LIST_CREATE_INTENT.search(message or ""):
        return False
    if is_multi_system_enrich_or_sync_intent(message or ""):
        return False
    return True


def already_existed_list_summary(
    *,
    name: str | None,
    list_id: str | None,
) -> str:
    """Honest summary: found shell list, did not populate contacts or sync CRM."""
    label = f'"{name}"' if name else "contact list"
    id_part = f" (id: {list_id})" if list_id else ""
    return (
        f"Found existing contact list {label}{id_part}. "
        "No contacts were added and no HubSpot sync ran — "
        "this is an idempotent find, not a populate or enrich action."
    )
