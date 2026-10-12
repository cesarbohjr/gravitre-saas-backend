"""Zendesk resolved tickets → RAG ingest jobs (STA-46)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.connectors.repository import get_decrypted_secret
from app.connectors.zendesk import ZendeskAPIError
from app.connectors.zendesk import _request as zendesk_request
from app.rag.ingest import create_ingest_job, create_source, get_source
from app.core.safe_dict import safe_normalize_stored_dict

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_HOURS = 24
# Per-run cap. Tickets are fetched oldest update first, so when the cap is hit the cursor
# stops at the last processed ticket and the next run continues from there.
MAX_TICKETS_PER_SYNC = 100  # same per-run volume as before Phase 1
SEARCH_PAGE_SIZE = 100
CURSOR_CONFIG_KEY = "zendesk_sync_cursor"
# Deletion propagation (SOURCE_DELETION_PROPAGATION_ENABLED): lower bound for the next
# read of the deleted-tickets listing. The listing is read oldest deletion first; the
# window advances to the last deletion read in order (or to the run start, less an
# overlap for clock skew, once the listing end is reached).
DELETED_CURSOR_CONFIG_KEY = "zendesk_deleted_scan_since"
MAX_DELETED_TICKETS_PER_SYNC = 1000
MAX_DELETED_PAGES_PER_SYNC = 50
DELETED_WINDOW_OVERLAP = timedelta(minutes=5)
# Check-by-id of indexed tickets, for deletions the listing no longer reports.
VERIFY_POSITION_CONFIG_KEY = "zendesk_verify_position"
VERIFY_BATCH_PER_SYNC = 25
# Zendesk keeps a deleted ticket in "Deleted tickets" (restorable) for 30 days, then
# scrubs it for good. Inside that window a ticket is only excluded from retrieval; a
# ticket we excluded that still answers 404 after the window is confirmed deleted.
SOFT_DELETE_RESTORE_WINDOW = timedelta(days=30)


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


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cursor(config: dict[str, Any], *, full_sync: bool) -> tuple[str, set[str]]:
    """(updated_at lower bound as ISO-8601 UTC, ticket ids already processed at that instant)."""
    if full_sync:
        return _iso_z(datetime.now(timezone.utc) - timedelta(days=30)), set()
    entry = config.get(CURSOR_CONFIG_KEY)
    if isinstance(entry, dict):
        since = _parse_ts(entry.get("updated_at"))
        if since:
            ids = entry.get("ids_at_since") or []
            return _iso_z(since), {str(i) for i in ids if i is not None}
    # Legacy connectors only have the run timestamp; fall back to it.
    last = _parse_ts(config.get("zendesk_last_synced_at"))
    if last:
        return _iso_z(last), set()
    return _iso_z(datetime.now(timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)), set()


def fetch_solved_tickets_since(
    subdomain: str,
    email: str | None,
    api_token: str | None,
    *,
    since_iso: str,
    max_records: int = MAX_TICKETS_PER_SYNC,
) -> list[dict[str, Any]]:
    """Solved tickets with updated_at >= since_iso, oldest update first, paginated up to max_records."""
    cap = max(int(max_records), 1)
    query = f"type:ticket status:solved updated>={since_iso}"
    tickets: list[dict[str, Any]] = []
    page = 1
    while len(tickets) < cap:
        data = zendesk_request(
            subdomain,
            email,
            api_token,
            "GET",
            "/search.json",
            params={
                "query": query,
                "sort_by": "updated_at",
                "sort_order": "asc",
                "per_page": SEARCH_PAGE_SIZE,
                "page": page,
            },
        )
        for item in data.get("results") or []:
            if not isinstance(item, dict):
                continue
            ticket = item.get("ticket") if item.get("result_type") == "ticket" and isinstance(item.get("ticket"), dict) else item
            if isinstance(ticket, dict):
                tickets.append(dict(ticket))
        if not data.get("next_page") or not data.get("results"):
            break
        page += 1
    return tickets[:cap]


def fetch_deleted_tickets_since(
    subdomain: str,
    email: str | None,
    api_token: str | None,
    *,
    since_iso: str,
    max_records: int = MAX_DELETED_TICKETS_PER_SYNC,
    max_pages: int = MAX_DELETED_PAGES_PER_SYNC,
) -> tuple[list[str], datetime | None, bool]:
    """Tickets deleted at or after ``since_iso`` (GET /deleted_tickets, oldest deletion first).

    Returns ``(ticket_ids, read_through, complete)``:

    * ``read_through``: ``deleted_at`` of the last in-window row read. Rows are read in
      ascending ``deleted_at`` order, so every deletion up to that instant has been seen
      and the window may advance to it (inclusive) even when the read stopped early.
    * ``complete``: True only when the end of the listing was reached.

    The read stops early (``complete=False``) after ``max_records`` rows strictly newer
    than ``since`` (rows exactly at ``since`` are re-read but not counted, so a window
    that advanced to an instant shared by many deletions still moves on), after
    ``max_pages`` pages, or on an empty page that still names a next page. A page that is
    not a list, or rows out of ascending order, raise ``ZendeskAPIError``: the window
    must never advance past rows that were not read.
    """
    cap = max(int(max_records), 1)
    since_dt = _parse_ts(since_iso)
    ids: list[str] = []
    read_through: datetime | None = None
    previous: datetime | None = None
    counted = 0
    for page in range(1, max(int(max_pages), 1) + 1):
        data = zendesk_request(
            subdomain,
            email,
            api_token,
            "GET",
            "/deleted_tickets.json",
            params={"sort_by": "deleted_at", "sort_order": "asc", "per_page": SEARCH_PAGE_SIZE, "page": page},
        )
        rows = data.get("deleted_tickets") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise ZendeskAPIError("Zendesk deleted tickets: malformed listing page")
        for row in rows:
            if not isinstance(row, dict):
                continue
            deleted_at = _parse_ts(row.get("deleted_at"))
            if deleted_at is None:
                continue
            if previous is not None and deleted_at < previous:
                raise ZendeskAPIError("Zendesk deleted tickets: listing not in ascending deleted_at order")
            previous = deleted_at
            if since_dt is not None and deleted_at < since_dt:
                continue
            if row.get("id") is not None:
                ids.append(str(row["id"]))
            read_through = deleted_at
            if since_dt is None or deleted_at > since_dt:
                counted += 1
        if not data.get("next_page"):
            return ids, read_through, True
        if not rows or counted >= cap:
            return ids, read_through, False
    return ids, read_through, False


def _exclude_soft_deleted_ticket_documents(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    source_id: str,
    subdomain: str,
    email: str,
    api_token: str,
    config: dict[str, Any],
    default_since: str,
    errors: list[str],
) -> int:
    """Exclude from retrieval the tickets Zendesk lists as deleted (off unless the flag is on).

    ``/deleted_tickets`` lists soft-deleted tickets, which an admin can still restore for
    30 days: their documents are excluded (reversible), never deleted here. Only tickets
    the listing names are excluded; a ticket missing from the solved-ticket search is
    never treated as deleted. ``config`` is updated in place:
    the window advances to the end of the listing (less a clock-skew overlap) after a
    complete read, or to the last deletion read in order after a partial one. In
    dry-run the window stays put, so nothing planned is skipped once dry-run is off.
    """
    from app.services.source_lifecycle import (
        deletion_dry_run,
        deletion_propagation_enabled,
        exclude_source_documents,
    )

    if not deletion_propagation_enabled(settings):
        return 0
    started = datetime.now(UTC)
    since = _parse_ts(config.get(DELETED_CURSOR_CONFIG_KEY))
    since_iso = _iso_z(since) if since else default_since
    try:
        ticket_ids, read_through, complete = fetch_deleted_tickets_since(
            subdomain, email, api_token, since_iso=since_iso, max_records=MAX_DELETED_TICKETS_PER_SYNC
        )
        removed = exclude_source_documents(
            client,
            settings,
            org_id=org_id,
            source_id=source_id,
            external_ids={f"zendesk:ticket:{tid}" for tid in ticket_ids},
            signal="zendesk_deleted_tickets",
            reason="soft_deleted",
        )
    except Exception as exc:  # noqa: BLE001
        # The window stays where it was; the next run reads it again.
        errors.append(f"deleted tickets: {exc}")
        return 0
    if deletion_dry_run(settings):
        return removed
    if complete:
        config[DELETED_CURSOR_CONFIG_KEY] = _iso_z(started - DELETED_WINDOW_OVERLAP)
        return removed
    since_dt = _parse_ts(since_iso)
    if read_through is not None and (since_dt is None or read_through > since_dt):
        config[DELETED_CURSOR_CONFIG_KEY] = _iso_z(read_through)
        errors.append(
            f"deleted tickets: read through {_iso_z(read_through)} of the window since {since_iso}; "
            "the rest is read next run"
        )
    else:
        errors.append(f"deleted tickets: listing incomplete since {since_iso}; read again next run")
    return removed


def _ticket_gone_checker(
    subdomain: str,
    email: str,
    api_token: str,
    *,
    client: Any = None,
    org_id: str = "",
    source_id: str = "",
):
    """``is_gone`` for the check-by-id pass.

    GET /tickets/{id} answers 404 for a soft-deleted ticket (still restorable) as well as
    for one deleted for good, so a 404 alone is not a confirmed deletion: it excludes the
    ticket (``EXCLUDE``). The deletion is confirmed (True, purge) only for a ticket this
    pipeline excluded more than ``SOFT_DELETE_RESTORE_WINDOW`` ago that still answers 404:
    by then Zendesk has scrubbed it and it can no longer be restored. A ticket returned
    with ``status: deleted`` is excluded; any other 200 is live (and restores an exclusion).
    """
    from app.services.source_lifecycle import EXCLUDE, excluded_since

    def is_gone(external_id: str) -> bool | str:
        ticket_id = external_id.removeprefix("zendesk:ticket:")
        try:
            data = zendesk_request(subdomain, email, api_token, "GET", f"/tickets/{ticket_id}.json")
        except ZendeskAPIError as exc:
            if exc.status_code != 404:
                raise
            since = (
                excluded_since(client, org_id=org_id, source_id=source_id, external_id=external_id)
                if client is not None
                else None
            )
            if since is not None and datetime.now(UTC) - since >= SOFT_DELETE_RESTORE_WINDOW:
                return True
            return EXCLUDE
        ticket = data.get("ticket") if isinstance(data, dict) else None
        if isinstance(ticket, dict) and str(ticket.get("status") or "").lower() == "deleted":
            return EXCLUDE
        return False

    return is_gone


def _verify_ticket_documents(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    source_id: str,
    subdomain: str,
    email: str,
    api_token: str,
    config: dict[str, Any],
    errors: list[str],
) -> int:
    """Check a batch of indexed tickets by id each run (deletions the listing no longer has).

    ``/deleted_tickets`` only lists soft-deleted tickets for about 30 days and never lists
    permanently deleted ones; a direct read is the only signal left (see
    ``_ticket_gone_checker`` for when it confirms a deletion).
    """
    from app.services.source_lifecycle import (
        deletion_propagation_enabled,
        verify_source_documents,
    )

    if not deletion_propagation_enabled(settings):
        return 0
    position = config.get(VERIFY_POSITION_CONFIG_KEY)
    position = dict(position) if isinstance(position, dict) else {}
    try:
        removed = verify_source_documents(
            client,
            settings,
            org_id=org_id,
            source_id=source_id,
            external_id_prefix="zendesk:ticket:",
            is_gone=_ticket_gone_checker(
                subdomain, email, api_token, client=client, org_id=org_id, source_id=source_id
            ),
            position=position,
            batch_size=VERIFY_BATCH_PER_SYNC,
            errors=errors,
            signal="zendesk_ticket_by_id",
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"verify tickets: {type(exc).__name__}: {exc}")
        return 0
    config[VERIFY_POSITION_CONFIG_KEY] = position
    return removed


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
    config = safe_normalize_stored_dict(connector, key='config')
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
    config = safe_normalize_stored_dict(connector, key='config')
    since_iso, seen_at_since = _cursor(config, full_sync=full_sync)
    source_id = ensure_zendesk_rag_source(client, org_id, connector, settings, created_by=actor_id)
    environment = str(connector.get("environment") or "production")

    job_ids: list[str] = []
    records_synced = 0
    errors: list[str] = []

    try:
        tickets = fetch_solved_tickets_since(
            subdomain,
            email,
            api_token,
            since_iso=since_iso,
            max_records=MAX_TICKETS_PER_SYNC,
        )
    except ZendeskAPIError as exc:
        raise ValueError(str(exc)) from exc

    has_more = len(tickets) >= MAX_TICKETS_PER_SYNC
    # Advance only to the last ticket that was queued successfully.
    cursor_dt = _parse_ts(since_iso)
    ids_at_cursor = set(seen_at_since)
    for ticket in tickets:
        tid = str(ticket.get("id") or "")
        updated = _parse_ts(ticket.get("updated_at"))
        if updated is not None and updated == cursor_dt and tid in seen_at_since:
            continue  # already queued on a previous run (>= boundary)
        try:
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
        except Exception as exc:  # noqa: BLE001
            # Stop here so the cursor never moves past an unprocessed ticket.
            errors.append(f"ticket {ticket.get('id')}: {exc}")
            has_more = True
            break
        job_ids.append(str(job["id"]))
        records_synced += 1
        if updated is not None:
            if cursor_dt is None or updated > cursor_dt:
                cursor_dt = updated
                ids_at_cursor = {tid}
            elif updated == cursor_dt:
                ids_at_cursor.add(tid)

    if has_more and records_synced == 0 and not errors:
        # A full page, all already processed at the cursor instant: more tickets share
        # this updated_at than one run can page through. Report it instead of looping.
        errors.append(f"cursor_stalled: more than {MAX_TICKETS_PER_SYNC} tickets updated at {since_iso}")
        logger.warning("zendesk_knowledge_sync_cursor_stalled org_id=%s since=%s", org_id, since_iso)
    documents_excluded = _exclude_soft_deleted_ticket_documents(
        client,
        settings,
        org_id=org_id,
        source_id=source_id,
        subdomain=subdomain,
        email=email,
        api_token=api_token,
        config=config,
        default_since=since_iso,
        errors=errors,
    )
    documents_removed = _verify_ticket_documents(
        client,
        settings,
        org_id=org_id,
        source_id=source_id,
        subdomain=subdomain,
        email=email,
        api_token=api_token,
        config=config,
        errors=errors,
    )
    cursor = {"updated_at": _iso_z(cursor_dt), "ids_at_since": sorted(ids_at_cursor)} if cursor_dt else None
    # ``zendesk_last_synced_at`` is the run time used for scheduling; the data cursor
    # lives in ``zendesk_sync_cursor``.
    config["zendesk_last_synced_at"] = _now_iso()
    if cursor is not None and not (full_sync and records_synced == 0):
        config[CURSOR_CONFIG_KEY] = cursor
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
        "documents_removed": documents_removed,
        "documents_excluded": documents_excluded,
        "job_ids": job_ids[:20],
        "errors": errors,
        "last_synced_at": config["zendesk_last_synced_at"],
        "cursor": config.get(CURSOR_CONFIG_KEY),
        "has_more": has_more,
    }
