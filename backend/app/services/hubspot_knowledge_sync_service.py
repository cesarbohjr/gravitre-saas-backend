"""HubSpot notes/emails → RAG ingest jobs (STA-46)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.connectors.hubspot import HubSpotAPIError, list_emails_since, list_notes_since
from app.connectors.hubspot_oauth import ensure_hubspot_access_token
from app.rag.ingest import create_ingest_job, create_source, get_source
from app.core.safe_dict import safe_normalize_stored_dict

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_HOURS = 24
# Per-object-type cap for one run. Records are fetched oldest change first, so when the
# cap is hit the per-type cursor stops at the last processed record and the next run
# continues from there (nothing beyond the cap is skipped).
MAX_OBJECTS_PER_SYNC = 100  # same per-run volume as before Phase 1
CURSORS_CONFIG_KEY = "hubspot_sync_cursors"


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


def _modified_ms(value: Any) -> int | None:
    """HubSpot ``hs_lastmodifieddate`` (ISO string or epoch ms) -> epoch ms."""
    if value is None or value == "":
        return None
    raw = str(value).strip()
    if raw.isdigit():
        return int(raw)
    parsed = _parse_ts(raw)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _kind_cursor(config: dict[str, Any], kind: str, *, full_sync: bool) -> tuple[int | None, set[str]]:
    """Per-object-type cursor: (since_ms, ids already processed at exactly since_ms)."""
    if full_sync:
        return None, set()
    cursors = config.get(CURSORS_CONFIG_KEY)
    entry = cursors.get(kind) if isinstance(cursors, dict) else None
    if isinstance(entry, dict) and entry.get("since_ms") is not None:
        try:
            since = int(entry["since_ms"])
        except (TypeError, ValueError):
            since = None
        if since is not None:
            ids = entry.get("ids_at_since") or []
            return since, {str(i) for i in ids if i is not None}
    # Legacy connectors only have the run timestamp; fall back to it.
    return _since_ms(config, full_sync=False), set()


def ensure_hubspot_rag_source(
    client: Any,
    org_id: str,
    connector: dict[str, Any],
    settings: Settings,
    *,
    created_by: str,
) -> str:
    config = safe_normalize_stored_dict(connector, key="config")
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

    config = safe_normalize_stored_dict(connector, key="config")
    source_id = ensure_hubspot_rag_source(client, org_id, connector, settings, created_by=actor_id)
    environment = str(connector.get("environment") or "production")

    job_ids: list[str] = []
    records_synced = 0
    errors: list[str] = []
    cursors = config.get(CURSORS_CONFIG_KEY)
    cursors = dict(cursors) if isinstance(cursors, dict) else {}
    has_more: dict[str, bool] = {}

    for fetcher, formatter, kind in (
        (list_notes_since, _format_note, "note"),
        (list_emails_since, _format_email, "email"),
    ):
        since_ms, seen_at_since = _kind_cursor(config, kind, full_sync=full_sync)
        try:
            items = fetcher(token, since_ms=since_ms, limit=MAX_OBJECTS_PER_SYNC)
        except HubSpotAPIError as exc:
            # Cursor for this kind stays where it was; the next run retries the same window.
            errors.append(f"{kind}: {exc}")
            continue
        has_more[kind] = len(items) >= MAX_OBJECTS_PER_SYNC
        # Advance only to the last record that was queued successfully.
        cursor_ms = since_ms
        ids_at_cursor = set(seen_at_since)
        synced_for_kind = 0
        kind_failed = False
        for item in items:
            rid = str(item.get("id") or "")
            props = item.get("properties") or {}
            modified_ms = _modified_ms(props.get("hs_lastmodifieddate"))
            if since_ms is not None and modified_ms == since_ms and rid in seen_at_since:
                continue  # already queued on a previous run (GTE boundary)
            try:
                title, text = formatter(item)
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
            except Exception as exc:  # noqa: BLE001
                # Stop here so the cursor never moves past an unprocessed record.
                errors.append(f"{kind} {item.get('id')}: {exc}")
                has_more[kind] = True
                kind_failed = True
                break
            job_ids.append(job_id)
            records_synced += 1
            synced_for_kind += 1
            if kind == "email":
                _queue_customer_message(client, settings, org_id=org_id, connector_id=connector_id, item=item)
            if modified_ms is not None:
                if cursor_ms is None or modified_ms > cursor_ms:
                    cursor_ms = modified_ms
                    ids_at_cursor = {rid}
                elif modified_ms == cursor_ms:
                    ids_at_cursor.add(rid)
        if has_more[kind] and synced_for_kind == 0 and not kind_failed:
            # A full page, all already processed at the cursor instant: more records share
            # this timestamp than one run can page through. Report it instead of looping.
            errors.append(f"{kind}: cursor_stalled: more than {MAX_OBJECTS_PER_SYNC} records modified at {since_ms}")
            logger.warning("hubspot_knowledge_sync_cursor_stalled org_id=%s kind=%s since_ms=%s", org_id, kind, since_ms)
        if cursor_ms is not None:
            cursors[kind] = {"since_ms": cursor_ms, "ids_at_since": sorted(ids_at_cursor)}

    entities = _write_company_entities(client, settings, org_id=org_id, token=token)

    # ``hubspot_last_synced_at`` is the run time used for scheduling; the data cursor lives
    # per object type in ``hubspot_sync_cursors``.
    config["hubspot_last_synced_at"] = _now_iso()
    config[CURSORS_CONFIG_KEY] = cursors
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
        "cursors": cursors,
        "has_more": any(has_more.values()),
        "entities": entities,
    }


def _queue_customer_message(
    client: Any, settings: Settings, *, org_id: str, connector_id: str, item: dict[str, Any]
) -> None:
    """Hand an inbound customer email to the observation consumer (Phase 3; off by default)."""
    from app.services.entity_observations import observations_enabled

    props = item.get("properties") or {}
    if not observations_enabled(settings) or props.get("hs_email_direction") != "INCOMING_EMAIL":
        return
    from app.services.customer_observation_feed import EVENT_CUSTOMER_MESSAGE, enqueue_customer_message

    enqueue_customer_message(
        client,
        org_id=org_id,
        system="hubspot",
        record_type="email",
        record_id=str(item.get("id") or ""),
        connector_id=connector_id,
        event_type=EVENT_CUSTOMER_MESSAGE,
    )


def _write_company_entities(client: Any, settings: Settings, *, org_id: str, token: str) -> dict[str, Any]:
    """File recent HubSpot companies into the entity store (Phase 2E; off by default)."""
    from app.services.entity_writer import (
        hubspot_company_records,
        write_provider_records,
        writer_enabled,
    )

    if not writer_enabled(settings):
        return {"skipped": "disabled"}
    try:
        from app.connectors.hubspot import list_companies

        payload = list_companies(token, properties=["name", "domain"], limit=100)
    except Exception as exc:  # noqa: BLE001
        logger.warning("hubspot_entity_feed_failed org_id=%s error=%s", org_id, exc)
        return {"error": type(exc).__name__}
    return write_provider_records(
        client, settings, org_id=org_id, records=hubspot_company_records(payload)
    ).as_dict()
