"""Zendesk resolved tickets → RAG ingest jobs (STA-46)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.connectors.repository import get_decrypted_secret
from app.connectors.zendesk import ZendeskAPIError, list_resolved_tickets_since
from app.rag.ingest import create_ingest_job, create_source, get_source

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_HOURS = 24
MAX_TICKETS_PER_SYNC = 100


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def zendesk_knowledge_sync_enabled(connector: dict[str, Any]) -> bool:
    config = connector.get("config") or {}
    if config.get("zendesk_knowledge_sync_enabled") is False:
        return False
    return True


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _since_date(config: dict[str, Any], *, full_sync: bool) -> str:
    if full_sync:
        return (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    last = _parse_ts(config.get("zendesk_last_synced_at"))
    if last:
        return last.strftime("%Y-%m-%d")
    return (datetime.now(timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)).strftime("%Y-%m-%d")


def _zendesk_credentials(
    client: Any,
    connector: dict[str, Any],
    connector_id: str,
    settings: Settings,
) -> tuple[str, str, str]:
    cfg = connector.get("config") or {}
    subdomain = str(cfg.get("subdomain") or cfg.get("zendesk_subdomain") or "").strip()
    if not subdomain:
        raise ValueError("Zendesk connector missing subdomain")
    email = get_decrypted_secret(client, connector_id, "email", settings)
    token = get_decrypted_secret(client, connector_id, "api_token", settings)
    if not email or not token:
        raise ValueError("Zendesk email/api_token secrets not configured")
    return subdomain, email, token


def ensure_zendesk_rag_source(
    client: Any,
    org_id: str,
    connector: dict[str, Any],
    settings: Settings,
    *,
    created_by: str,
) -> str:
    config = dict(connector.get("config") or {})
    existing = config.get("zendesk_rag_source_id")
    environment = str(connector.get("environment") or "production")
    if existing and get_source(client, org_id, str(existing), environment_name=environment):
        return str(existing)

    name = connector.get("name") or "Zendesk"
    source = create_source(
        client,
        org_id,
        title=f"Zendesk — {name}",
        type_="zendesk",
        metadata={"connector_id": connector.get("id"), "source": "resolved_tickets"},
        created_by=created_by,
        environment_name=environment,
        department_id=str(config["zendesk_department_id"]) if config.get("zendesk_department_id") else None,
    )
    source_id = str(source["id"])
    config["zendesk_rag_source_id"] = source_id
    client.table("connectors").update({"config": config}).eq("id", connector["id"]).eq("org_id", org_id).execute()
    return source_id


def _ticket_text(ticket: dict[str, Any]) -> str:
    tid = ticket.get("id")
    subject = str(ticket.get("subject") or "").strip() or f"Ticket {tid}"
    description = str(ticket.get("description") or "").strip()
    status = ticket.get("status")
    priority = ticket.get("priority")
    parts = [f"Subject: {subject}", f"Status: {status}", f"Priority: {priority}"]
    if description:
        parts.append("")
        parts.append(description)
    return "\n".join(parts)


def run_zendesk_knowledge_sync(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    actor_id: str,
    full_sync: bool = False,
) -> dict[str, Any]:
    row = (
        client.table("connectors")
        .select("id,name,config,environment,status")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise ValueError("Connector not found")
    connector = dict(row.data[0])
    if not zendesk_knowledge_sync_enabled(connector):
        raise ValueError("Zendesk knowledge sync is disabled for this connector")

    subdomain, email, api_token = _zendesk_credentials(client, connector, connector_id, settings)
    config = dict(connector.get("config") or {})
    since_date = _since_date(config, full_sync=full_sync)
    source_id = ensure_zendesk_rag_source(client, org_id, connector, settings, created_by=actor_id)
    environment = str(connector.get("environment") or "production")

    job_ids: list[str] = []
    records_synced = 0
    errors: list[str] = []

    try:
        tickets = list_resolved_tickets_since(
            subdomain,
            email,
            api_token,
            since_date=since_date,
            limit=MAX_TICKETS_PER_SYNC,
        )
    except ZendeskAPIError as exc:
        raise ValueError(str(exc)) from exc

    for ticket in tickets:
        try:
            tid = str(ticket.get("id") or "")
            subject = str(ticket.get("subject") or "").strip() or f"Ticket {tid}"
            text = _ticket_text(ticket)
            job = create_ingest_job(
                client,
                org_id,
                source_id,
                external_id=f"zendesk:ticket:{tid}",
                created_by=actor_id,
                request_payload={
                    "title": subject,
                    "external_id": f"zendesk:ticket:{tid}",
                    "text": text,
                    "metadata": {
                        "zendesk_ticket_id": tid,
                        "zendesk_status": ticket.get("status"),
                        "zendesk_updated_at": ticket.get("updated_at"),
                    },
                },
                environment_name=environment,
            )
            job_ids.append(str(job["id"]))
            records_synced += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ticket {ticket.get('id')}: {exc}")

    config["zendesk_last_synced_at"] = _now_iso()
    config["zendesk_rag_source_id"] = source_id
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()

    logger.info(
        "zendesk_knowledge_sync org_id=%s connector_id=%s tickets=%s jobs=%s",
        org_id,
        connector_id,
        records_synced,
        len(job_ids),
    )
    return {
        "source_id": source_id,
        "pages_synced": records_synced,
        "jobs_queued": len(job_ids),
        "job_ids": job_ids[:20],
        "errors": errors,
        "last_synced_at": config["zendesk_last_synced_at"],
    }
