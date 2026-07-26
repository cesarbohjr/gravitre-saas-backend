"""Module B phase 2 — cross-conversation entity memory (feature-flagged OFF).

Uses existing ``entity_resolution_store`` / ``org_entity_resolution_records`` so a
Slack channel or email recipient confirmed in conversation A can be recalled in
conversation B. Does **not** invent a parallel memory system.

Gated by ``Settings.cross_conversation_ledger_memory_enabled`` (default True).
Uses durable ``org_entity_resolution_records`` — no parallel memory store.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.confidence_honesty import CONFIDENCE_SOURCE_HEURISTIC, estimated_confidence
from app.services.entity_resolution_store import (
    lookup_fuzzy_resolutions,
    lookup_resolutions,
    upsert_resolution,
)
from app.services.parameter_ledger import ParameterLedger, get_ledger

logger = get_logger(__name__)

# Slot keys we may promote / recall across conversations.
_CROSS_SLOT_TYPES: dict[str, str] = {
    "to": "email_recipient",
    "email": "email_recipient",
    "channel": "slack_channel",
}


def _ledger_edge_confidence() -> float:
    """Module C: ledger promotions store a heuristic estimate, not a learned score."""
    return float(estimated_confidence(0.9, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"])


def feature_enabled(settings: Settings | None = None) -> bool:
    return bool((settings or get_settings()).cross_conversation_ledger_memory_enabled)


def promote_confirmed_ledger_slots(
    client: Any,
    *,
    org_id: str,
    conversation_id: str | None,
    task_state: dict[str, Any] | None,
    integration: str = "conversation",
    settings: Settings | None = None,
) -> int:
    """Persist high-confidence ledger slots into entity_resolution_store.

    No-op when the feature flag is off. Never raises.
    """
    if not feature_enabled(settings):
        return 0
    if not client or not org_id:
        return 0
    ledger = get_ledger(task_state)
    written = 0
    for slot_key, entity_type in _CROSS_SLOT_TYPES.items():
        value = ledger.get(slot_key)
        if not value:
            continue
        slot = ledger.slots.get(slot_key)
        if slot is None or (slot.confidence or "high").lower() != "high":
            continue
        # entity_id is the canonical value itself for email/channel aliases.
        ok = upsert_resolution(
            client,
            org_id=org_id,
            alias=value,
            entity_type=entity_type,
            entity_id=value,
            integration=integration if slot_key == "channel" else "email",
            source="parameter_ledger_confirmed",
            confidence=_ledger_edge_confidence(),
            conversation_id=conversation_id,
        )
        if ok:
            written += 1
        # Also alias first-token of email local part when dotted (Sarah → full addr
        # is in-conversation promote; here we store the full address as alias+id).
    if written:
        logger.info(
            "cross_conversation_ledger_promoted org_id=%s count=%s conversation_id=%s",
            org_id,
            written,
            conversation_id,
        )
    return written


def recall_slots_into_ledger(
    client: Any,
    *,
    org_id: str,
    ledger: ParameterLedger,
    aliases: list[str],
    settings: Settings | None = None,
) -> ParameterLedger:
    """Fill empty ledger slots from durable entity resolutions (flag-gated).

    Only writes **medium** confidence — in-conversation high-confidence still wins,
    and medium values require propose/confirm before silent use.
    """
    if not feature_enabled(settings):
        return ledger
    if not client or not org_id or not aliases:
        return ledger
    hits = lookup_resolutions(client, org_id, aliases, limit=20)
    seen_aliases = {h.alias_normalized for h in hits}
    for alias in aliases:
        for hit in lookup_fuzzy_resolutions(
            client,
            org_id,
            alias,
            limit=10,
        ):
            if hit.alias_normalized not in seen_aliases:
                hits.append(hit)
                seen_aliases.add(hit.alias_normalized)
    for hit in hits:
        if hit.confidence < 0.7:
            continue
        if hit.entity_type == "email_recipient" and not ledger.get("to"):
            ledger.upsert(
                "to",
                hit.entity_id,
                source="cross_conversation_entity_memory",
                confidence="medium",
            )
            ledger.upsert(
                "email",
                hit.entity_id,
                source="cross_conversation_entity_memory",
                confidence="medium",
            )
        elif hit.entity_type == "slack_channel" and not ledger.get("channel"):
            ledger.upsert(
                "channel",
                hit.entity_id,
                source="cross_conversation_entity_memory",
                confidence="medium",
            )
    return ledger
