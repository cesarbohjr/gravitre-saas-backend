"""Phase 3 feed: customer messages reach the observation extractor through the outbox.

A sync that sees an inbound customer email enqueues a thin
``customer.message_received`` event (ids only). The relay hands it to
``handle_customer_message``, which re-reads the message from the provider,
finds the business entity it is about, and runs ``observe_customer_message``.
Going through the outbox keeps model calls off the sync path and gives retries
with backoff for free.

Today's source: HubSpot inbound emails associated with a company that the entity
writer has already filed. A message with no filed entity is skipped, never
guessed.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.domain_events import enqueue_domain_event, handlers_for, register_domain_event_handler

logger = get_logger(__name__)

EVENT_CUSTOMER_MESSAGE = "customer.message_received"
HANDLER_NAME = "entity_observations.observe_customer_message"


def enqueue_customer_message(
    client: Any,
    *,
    org_id: str,
    system: str,
    record_type: str,
    record_id: str,
    connector_id: str,
    event_type: str = EVENT_CUSTOMER_MESSAGE,
) -> bool:
    if not record_id:
        return False
    return enqueue_domain_event(
        client,
        org_id=org_id,
        event_type=event_type,
        aggregate_type=f"{system}_{record_type}",
        aggregate_id=record_id,
        idempotency_key=f"{system}:{record_type}:{record_id}",
        payload={"system": system, "record_type": record_type, "record_id": record_id, "connector_id": connector_id},
    )


def _entity_row_for(client: Any, org_id: str, system: str, resource_type: str, resource_ids: list[str]) -> str | None:
    if not resource_ids:
        return None
    res = (
        client.table("org_business_entity_bindings")
        .select("entity_id, resource_id")
        .eq("org_id", org_id)
        .eq("system", system)
        .eq("resource_type", resource_type)
        .in_("resource_id", resource_ids)
        .execute()
    )
    entity_ids = {str(r["entity_id"]) for r in res.data or [] if r.get("entity_id")}
    # Exactly one entity, or we cannot say who the message is about.
    return entity_ids.pop() if len(entity_ids) == 1 else None


MAX_MEMBER_LOOKUP = 5000


def org_internal_identities(client: Any, org_id: str, host: str) -> tuple[set[str], set[str]]:
    """Domains and addresses that mean "a colleague wrote this", never a customer.

    The org's website host plus every member's address; a member's domain counts
    too unless it is shared consumer mail. Raises on lookup failure so the relay
    retries instead of observing a colleague as a customer.
    """
    from app.services.entity_observations import FREE_MAIL_DOMAINS

    members = (
        client.table("organization_members").select("user_id").eq("org_id", org_id).limit(MAX_MEMBER_LOOKUP).execute()
    )
    user_ids = sorted({str(r["user_id"]) for r in members.data or [] if r.get("user_id")})
    emails: set[str] = set()
    for i in range(0, len(user_ids), 200):
        rows = client.table("users").select("email").in_("auth_user_id", user_ids[i : i + 200]).execute()
        emails.update(str(r["email"]).strip().lower() for r in rows.data or [] if r.get("email"))
    domains = {host} if host else set()
    domains.update(
        d for d in (e.rsplit("@", 1)[-1] for e in emails if "@" in e) if d and d not in FREE_MAIL_DOMAINS
    )
    return domains, emails


def handle_customer_message(client: Any, event: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    from app.services.entity_observations import CustomerMessage, observe_customer_message, observations_enabled

    settings = settings or get_settings()
    from app.core.ingestion_kill_switch import ingestion_disabled

    if not observations_enabled(settings):
        return {"skipped": "disabled"}
    if ingestion_disabled(settings):
        # Same outcome as the feature being off: the event is handled, nothing is read or written.
        return {"skipped": "ingestion_disabled"}
    payload =event.get("payload") if isinstance(event.get("payload"), dict) else {}
    org_id = str(event.get("org_id") or "")
    if payload.get("system") != "hubspot" or payload.get("record_type") != "email":
        return {"skipped": "unsupported_source"}
    from app.connectors import hubspot as hs
    from app.connectors.hubspot_oauth import ensure_hubspot_access_token

    token, err = ensure_hubspot_access_token(
        client, org_id, str(payload.get("connector_id") or ""), settings, validate_remote=False
    )
    if err or not token:
        return {"skipped": "not_connected"}  # a disconnected source is not retried
    record_id = str(payload.get("record_id") or "")
    email = hs.get_email(token, record_id)
    props = email.get("properties") or {}
    if props.get("hs_email_direction") != "INCOMING_EMAIL":
        return {"skipped": "not_inbound"}
    companies = hs.email_company_associations(token, [record_id]).get(record_id, [])
    entity_row_id = _entity_row_for(client, org_id, "hubspot", "company", companies)
    if not entity_row_id:
        return {"skipped": "no_single_entity"}
    from app.services.org_business_identity import load_org_business_identity

    host = str(load_org_business_identity(client, org_id).get("host") or "")
    org_domains, org_emails = org_internal_identities(client, org_id, host)
    message = CustomerMessage(
        text=f"Subject: {props.get('hs_email_subject') or ''}\n\n{props.get('hs_email_text') or ''}".strip(),
        source_system="hubspot",
        source_record_type="email",
        source_record_id=record_id,
        observed_at=str(props.get("hs_timestamp") or event.get("created_at") or ""),
        author_email=str(props.get("hs_email_from_email") or ""),
    )
    # The relay runs handlers in a worker thread with no running event loop.
    result = asyncio.run(
        observe_customer_message(
            client,
            settings,
            org_id=org_id,
            entity_row_id=entity_row_id,
            message=message,
            org_domains=org_domains,
            org_emails=org_emails,
        )
    )
    if result.get("skipped") == "error":
        raise RuntimeError("observation extraction failed")  # the relay retries with backoff
    return result


def register_customer_observation_handlers() -> None:
    if any(r.name == HANDLER_NAME for r in handlers_for(EVENT_CUSTOMER_MESSAGE)):
        return
    register_domain_event_handler(
        EVENT_CUSTOMER_MESSAGE, HANDLER_NAME, lambda client, event: handle_customer_message(client, event)
    )
