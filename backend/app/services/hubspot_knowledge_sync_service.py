"""HubSpot notes/emails → RAG ingest jobs (STA-46)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.connectors.hubspot import HubSpotAPIError, list_emails_since, list_notes_since
from app.connectors.hubspot_oauth import ensure_hubspot_access_token
from app.rag.ingest import create_ingest_job, create_source, get_source

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_HOURS = 24
MAX_OBJECTS_PER_SYNC = 100


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hubspot_knowledge_sync_enabled(connector: dict[str, Any]) -> bool:
    config = connector.get("config") or {}
    if config.get("hubspot_knowledge_sync_enabled") is False:
        return False
    return True


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _since_ms(config: dict[str, Any], *, full_sync: bool) -> int | None:
    if full_sync:
        return None
    last = _parse_ts(config.get("hubspot_last_synced_at"))
    if last:
        return int(last.timestamp() * 1000)
    return int((datetime.now(timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)).timestamp() * 1000)


def ensure_hubspot_rag_source(
    client: Any,
    org_id: str,
    connector: dict[str, Any],
    settings: Settings,
    *,
    created_by: str,
) -> str:
    config = dict(connector.get("config") or {})
    existing = config.get("hubspot_rag_source_id")
    environment = str(connector.get("environment") or "production")
    if existing and get_source(client, org_id, str(existing), environment_name=environment):
        return str(existing)

    name = connector.get("name") or "HubSpot"
    source = create_source(
        client,
        org_id,
        title=f"HubSpot — {name}",
        type_="hubspot",
        metadata={"connector_id": connector.get("id"), "source": "notes_and_emails"},
        created_by=created_by,
        environment_name=environment,
        department_id=str(config["hubspot_department_id"]) if config.get("hubspot_department_id") else None,
    )
    source_id = str(source["id"])
    config["hubspot_rag_source_id"] = source_id
    client.table("connectors").update({"config": config}).eq("id", connector["id"]).eq("org_id", org_id).execute()
    return source_id


def _format_note(record: dict[str, Any]) -> tuple[str, str]:
    rid = str(record.get("id") or "")
    props = record.get("properties") or {}
    body = str(props.get("hs_note_body") or "").strip()
    title = f"HubSpot note {rid}"
    text = body or "(empty note)"
    return title, text


def _format_email(record: dict[str, Any]) -> tuple[str, str]:
    rid = str(record.get("id") or "")
    props = record.get("properties") or {}
    subject = str(props.get("hs_email_subject") or "").strip() or f"Email {rid}"
    body = str(props.get("hs_email_text") or "").strip()
    text = f"Subject: {subject}\n\n{body or '(empty email body)'}"
    return subject, text


def _queue_ingest(
    client: Any,
    *,
    org_id: str,
    source_id: str,
    external_id: str,
    title: str,
    text: str,
    created_by: str,
    environment_name: str,
    metadata: dict[str, Any],
) -> str:
    job = create_ingest_job(
        client,
        org_id,
        source_id,
        external_id=external_id,
        created_by=created_by,
        request_payload={
            "title": title,
            "external_id": external_id,
            "text": text,
            "metadata": metadata,
        },
        environment_name=environment_name,
    )
    return str(job["id"])


def run_hubspot_knowledge_sync(
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
    if not hubspot_knowledge_sync_enabled(connector):
        raise ValueError("HubSpot knowledge sync is disabled for this connector")

    token, err = ensure_hubspot_access_token(
        client,
        org_id,
        connector_id,
        settings,
        environment_name=str(connector.get("environment") or "production"),
        validate_remote=False,
    )
    if err or not token:
        raise ValueError(err or "HubSpot not connected")

    config = dict(connector.get("config") or {})
    since_ms = _since_ms(config, full_sync=full_sync)
    source_id = ensure_hubspot_rag_source(client, org_id, connector, settings, created_by=actor_id)
    environment = str(connector.get("environment") or "production")

    job_ids: list[str] = []
    records_synced = 0
    errors: list[str] = []

    for fetcher, formatter, kind in (
        (list_notes_since, _format_note, "note"),
        (list_emails_since, _format_email, "email"),
    ):
        try:
            items = fetcher(token, since_ms=since_ms, limit=MAX_OBJECTS_PER_SYNC)
        except HubSpotAPIError as exc:
            errors.append(f"{kind}: {exc}")
            continue
        for item in items:
            try:
                title, text = formatter(item)
                rid = str(item.get("id") or "")
                props = item.get("properties") or {}
                job_id = _queue_ingest(
                    client,
                    org_id=org_id,
                    source_id=source_id,
                    external_id=f"hubspot:{kind}:{rid}",
                    title=title,
                    text=text,
                    created_by=actor_id,
                    environment_name=environment,
                    metadata={
                        "hubspot_object_type": kind,
                        "hubspot_object_id": rid,
                        "hubspot_lastmodified": props.get("hs_lastmodifieddate"),
                    },
                )
                job_ids.append(job_id)
                records_synced += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{kind} {item.get('id')}: {exc}")

    config["hubspot_last_synced_at"] = _now_iso()
    config["hubspot_rag_source_id"] = source_id
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()

    logger.info(
        "hubspot_knowledge_sync org_id=%s connector_id=%s records=%s jobs=%s",
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
        "last_synced_at": config["hubspot_last_synced_at"],
    }
