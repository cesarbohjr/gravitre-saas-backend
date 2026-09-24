"""3.0-H natural-language answer from accepted BusinessEntity store.

Does not invent joins. Does not live-read a disconnected provider.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.business_entity_fabric import load_accepted_entities
from app.services.clarification_policy import format_not_connected_message
from app.services.connector_semantic_registry import connector_display_name

_CROSS = re.compile(
    r"(?is)\b("
    r"same (?:company|customer|account|entity)"
    r"|across (?:systems|hubspot|quickbooks|zendesk)"
    r"|hubspot and (?:quickbooks|zendesk|qbo)"
    r"|(?:quickbooks|zendesk) and hubspot"
    r"|cross[- ]system"
    r")\b"
)


def match_cross_system_entity_intent(message: str) -> bool:
    return bool(_CROSS.search(message or ""))


@dataclass(frozen=True)
class EntityJoinIntent:
    display_name: str | None


def entity_join_intent(message: str) -> EntityJoinIntent | None:
    if not match_cross_system_entity_intent(message or ""):
        return None
    named = re.search(
        r"(?is)\babout\s+([A-Za-z][\w&'. -]{0,40}?)\s+across\b",
        message or "",
    )
    display_name = named.group(1).strip() if named else None
    return EntityJoinIntent(display_name=display_name)


def try_cross_system_entity_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    connected_integrations: list[str] | None,
) -> dict[str, Any] | None:
    if not match_cross_system_entity_intent(message or ""):
        return None
    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}
    entities = load_accepted_entities(client, org_id)
    companies = [row for row in entities if row.kind == "company" and len(row.bindings) >= 2]
    wanted = (entity_join_intent(message) or EntityJoinIntent(None)).display_name
    if wanted:
        named = [
            row
            for row in companies
            if row.display_name.strip().lower() == wanted.strip().lower()
        ]
        if named:
            companies = named
        elif companies:
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": (
                    f"I have accepted joins in this organization, but none named “{wanted}”. "
                    "I will not treat a similar display name as the same company."
                ),
                "workflow_status": "completed",
                "execution_path": "entity_join_store",
                "join": False,
                "writes_started": False,
            }
    if not companies:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                "I don't have an accepted cross-system company join for this organization. "
                "Matching names is not enough, so I am keeping HubSpot, QuickBooks, and Zendesk "
                "records separate until there is exact host or email evidence."
            ),
            "workflow_status": "completed",
            "execution_path": "entity_join_store",
            "join": False,
            "writes_started": False,
        }
    entity = companies[0]
    systems = sorted({b.system for b in entity.bindings if b.system})
    hosts = sorted(
        {e.value for e in entity.evidence if e.kind == "host"}
        | {e.value for b in entity.bindings for e in b.evidence if e.kind == "host"}
    )
    missing = [
        format_not_connected_message(vendor, display_name=connector_display_name(vendor))
        for vendor in systems
        if vendor not in connected
    ]
    fact = (
        f"The accepted company entity “{entity.display_name}” links {', '.join(systems)} "
        f"on stored evidence"
        + (f" (host {', '.join(hosts)})" if hosts else "")
        + f". Entity id {entity.id}."
    )
    inference = (
        "That join is from the tenant entity store, not a live multi-provider census. "
        "I will not mix metrics from those systems as if they were one result set."
    )
    if missing:
        limitation = " ".join(missing)
    else:
        limitation = "I can read each connected system separately if you want live records."
    body = f"{fact}\n\n{inference}\n\n{limitation}"
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": body,
        "workflow_status": "completed",
        "execution_path": "entity_join_store",
        "join": True,
        "entity_id": entity.id,
        "systems": systems,
        "missing_live_sources": missing,
        "writes_started": False,
        "task_state": {"business_entity": entity.as_dict(), "capability_id": "entity.join.store"},
    }
