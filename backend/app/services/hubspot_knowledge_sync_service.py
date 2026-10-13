"""HubSpot notes/emails → RAG ingest jobs (STA-46)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.connectors.hubspot import (
    HubSpotAPIError,
    CRM_OBJECT_ARCHIVED,
    CRM_OBJECT_DELETED,
    crm_object_state,
    list_archived_objects,
    list_emails_since,
    list_notes_since,
)
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
# Deletion propagation (SOURCE_DELETION_PROPAGATION_ENABLED). Archived records sit in
# HubSpot's recycle bin and can be restored, so they are excluded from retrieval, never
# deleted; only a record HubSpot confirms is gone for good (404 on a plain read AND on an
# ``archived=true`` read) has its documents removed. The archived listing is paged
# by record id, not by archive time, so each run reads the next slice and the position wraps
# to the start once the listing is exhausted. Every archived record is seen within a cycle.
ARCHIVED_CURSORS_CONFIG_KEY = "hubspot_archived_cursors"
MAX_ARCHIVED_PER_SYNC = 500
# Check-by-id of indexed notes/emails, for permanent deletes no listing reports.
VERIFY_POSITION_CONFIG_KEY = "hubspot_verify_position"
VERIFY_BATCH_PER_SYNC = 25
_ARCHIVE_OBJECT_TYPES = (("note", "notes"), ("email", "emails"))


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
    from app.services.ingestion_interlock import ensure_existing_ingestion_allowed

    # No-op unless EXISTING_INGESTION_REQUIRES_LIFECYCLE=true (owner switch, default off).
    ensure_existing_ingestion_allowed(settings, "hubspot")
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

    propagation = _propagate_upstream_removals(
        client, settings, org_id=org_id, source_id=source_id, token=token, config=config, errors=errors
    )

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
        "documents_removed": propagation["removed"],
        "documents_excluded": propagation["excluded"],
        "job_ids": job_ids[:20],
        "errors": errors,
        "last_synced_at": config["hubspot_last_synced_at"],
        "cursors": cursors,
        "has_more": any(has_more.values()),
        "entities": entities,
    }


def _propagate_upstream_removals(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    source_id: str,
    token: str,
    config: dict[str, Any],
    errors: list[str],
) -> dict[str, int]:
    """Exclude archived notes/emails, remove confirmed-deleted ones (off unless the flag is on).

    Only records the archived listing returns with ``archived: true`` are excluded from
    retrieval (reversible: HubSpot can restore them); a record missing from an incremental
    page is never treated as deleted. Permanent removal happens only in the check-by-id
    pass, on HubSpot's confirmation. ``config`` is updated in place with the next listing
    position; on a listing error the position stays put.
    """
    from app.services.source_lifecycle import (
        deletion_propagation_enabled,
        exclude_source_documents,
    )

    if not deletion_propagation_enabled(settings):
        return {"removed": 0, "excluded": 0}
    positions = config.get(ARCHIVED_CURSORS_CONFIG_KEY)
    positions = dict(positions) if isinstance(positions, dict) else {}
    excluded = 0
    for kind, object_type in _ARCHIVE_OBJECT_TYPES:
        after = positions.get(kind)
        try:
            records, next_after = list_archived_objects(
                token, object_type, after=str(after) if after else None, max_records=MAX_ARCHIVED_PER_SYNC
            )
        except Exception as exc:  # noqa: BLE001
            # Any listing failure (API error, undecodable body) keeps the position and
            # never fails the sync after its ingest jobs were queued.
            errors.append(f"{kind} archived: {type(exc).__name__}: {exc}")
            continue
        external_ids = {
            f"hubspot:{kind}:{r.get('id')}"
            for r in records
            if isinstance(r, dict) and r.get("id") and r.get("archived") is True
        }
        try:
            excluded += exclude_source_documents(
                client,
                settings,
                org_id=org_id,
                source_id=source_id,
                external_ids=external_ids,
                signal="hubspot_archived",
            )
        except Exception as exc:  # noqa: BLE001
            # Keep the listing position so the same slice is read again next run.
            errors.append(f"{kind} archived exclusion: {exc}")
            continue
        if next_after:
            positions[kind] = next_after
        else:
            positions.pop(kind, None)
    config[ARCHIVED_CURSORS_CONFIG_KEY] = positions
    removed = _verify_record_documents(
        client, settings, org_id=org_id, source_id=source_id, token=token, config=config, errors=errors
    )
    return {"removed": removed, "excluded": excluded}


def _record_gone_checker(token: str):
    """``is_gone`` for the check-by-id pass over ``hubspot:{note|email}:{id}`` documents.

    True (purge) only when HubSpot confirms permanent deletion; ``EXCLUDE`` for an
    archived record; False when present (which also restores an excluded record).
    """
    from app.services.source_lifecycle import EXCLUDE

    def is_gone(external_id: str) -> bool | str:
        parts = external_id.split(":", 2)
        if len(parts) != 3 or parts[1] not in {"note", "email"} or not parts[2]:
            return False  # not a record this sync indexes: never removed here
        state = crm_object_state(token, f"{parts[1]}s", parts[2])
        if state == CRM_OBJECT_DELETED:
            return True
        if state == CRM_OBJECT_ARCHIVED:
            return EXCLUDE
        return False

    return is_gone


def _verify_record_documents(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    source_id: str,
    token: str,
    config: dict[str, Any],
    errors: list[str],
) -> int:
    """Check a batch of indexed notes/emails by id each run.

    The archived listing only holds soft-deleted records (the recycle bin); records
    deleted permanently (GDPR delete, or purged from the bin) appear in no listing, and a
    404 on a direct read is the only signal left. Every document is checked once per
    rotation of ``hubspot_verify_position``.
    """
    from app.services.source_lifecycle import verify_source_documents

    position = config.get(VERIFY_POSITION_CONFIG_KEY)
    position = dict(position) if isinstance(position, dict) else {}
    try:
        removed = verify_source_documents(
            client,
            settings,
            org_id=org_id,
            source_id=source_id,
            external_id_prefix="hubspot:",
            is_gone=_record_gone_checker(token),
            position=position,
            batch_size=VERIFY_BATCH_PER_SYNC,
            errors=errors,
            signal="hubspot_record_by_id",
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"verify records: {type(exc).__name__}: {exc}")
        return 0
    config[VERIFY_POSITION_CONFIG_KEY] = position
    return removed


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
    from app.core.ingestion_kill_switch import ingestion_disabled
    from app.services.entity_writer import (
        hubspot_company_records,
        write_provider_records,
        writer_enabled,
    )

    if not writer_enabled(settings):
        return {"skipped": "disabled"}
    if ingestion_disabled(settings):
        # Checked before the provider read, so the kill switch costs no HubSpot call.
        return {"skipped": "ingestion_disabled"}
    try:
        from app.connectors.hubspot import list_companies

        payload = list_companies(token, properties=["name", "domain"], limit=100)
    except Exception as exc:  # noqa: BLE001
        logger.warning("hubspot_entity_feed_failed org_id=%s error=%s", org_id, exc)
        return {"error": type(exc).__name__}
    return write_provider_records(
        client, settings, org_id=org_id, records=hubspot_company_records(payload)
    ).as_dict()
