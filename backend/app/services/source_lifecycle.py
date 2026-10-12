"""Phase 2B source lifecycle: what happens to a source's data when it goes away.

Three pieces, each off until switched on:

* ``revoke_on_disconnect`` runs inside the disconnect request, before our copy of the
  tokens is dropped, and asks the provider to revoke the grant
  (CONNECTOR_PROVIDER_REVOKE_ON_DISCONNECT).
* ``handle_source_disconnected`` consumes the ``source.disconnected`` outbox event and
  removes the data derived from that connector in one database transaction
  (``purge_connector_derived_data``). It writes a dry-run receipt only, until
  SOURCE_PURGE_DRY_RUN=false. Runs only when the relay is on.
* ``reconcile_source_documents`` removes indexed documents a complete full-sweep sync no
  longer finds upstream AND the provider confirms are gone (SOURCE_DELETION_PROPAGATION_ENABLED).
* ``remove_source_documents`` removes the documents of records the provider itself
  reports as deleted, archived or trashed during an incremental sync (same flag).
* ``verify_source_documents`` checks indexed documents by id, a batch per run, for
  deletions no provider listing reports (same flag).

Deletion propagation honours SOURCE_PURGE_DRY_RUN and writes audit receipts; see the
safety rules above ``SAFETY_CAP_FRACTION``.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.config import Settings, get_settings
from app.connectors.provider_revoke import (
    GOOGLE_FAMILY,
    RevokeOutcome,
    canonical_vendor,
    revoke_provider_tokens,
)
from app.core.logging import get_logger
from app.services.domain_events import (
    EVENT_SOURCE_DISCONNECTED,
    handlers_for,
    register_domain_event_handler,
)

logger = get_logger(__name__)

PURGE_HANDLER_NAME = "source_lifecycle.purge_derived_data"
SYSTEM_ACTOR = "system:source_lifecycle"

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


class SourcePurgeError(RuntimeError):
    """Raised so the relay retries the event (with backoff, then dead-letter)."""


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    p = event.get("payload")
    return p if isinstance(p, dict) else {}


def _connector_row(client: Any, org_id: str, connector_id: str) -> dict[str, Any] | None:
    res = (
        client.table("connectors")
        .select("id, org_id, vendor, type, deleted_at")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def handle_source_disconnected(client: Any, event: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    """Outbox handler for ``source.disconnected``. Idempotent; raises to retry."""
    settings = settings or get_settings()
    payload = _payload(event)
    org_id = str(event.get("org_id") or "")
    connector_id = str(payload.get("connector_id") or event.get("aggregate_id") or "")
    disconnected_at = payload.get("deleted_at")
    if not _UUID_RE.match(org_id) or not _UUID_RE.match(connector_id) or not disconnected_at:
        # Malformed events can never succeed; record and complete instead of retrying.
        logger.error(
            "source_purge_skipped_malformed event_id=%s org_id=%r connector_id=%r",
            event.get("event_id"),
            org_id,
            connector_id,
        )
        return {"skipped": "malformed"}

    row = _connector_row(client, org_id, connector_id)
    vendor = canonical_vendor((row or {}).get("vendor") or (row or {}).get("type") or payload.get("connector_type"))
    # Anything but an explicit False keeps the purge a plan.
    dry_run = getattr(settings, "source_purge_dry_run", True) is not False
    try:
        res = client.rpc(
            "purge_connector_derived_data",
            {
                "p_org_id": org_id,
                "p_connector_id": connector_id,
                "p_vendor": vendor,
                "p_disconnected_at": disconnected_at,
                "p_dry_run": dry_run,
                "p_event_id": event.get("event_id"),
            },
        ).execute()
    except Exception as exc:
        raise SourcePurgeError(f"purge rpc failed: {type(exc).__name__}: {exc}") from exc
    counts = res.data if isinstance(res.data, dict) else {}

    from app.workflows.audit import write_audit_event

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=SYSTEM_ACTOR,
        action="connector.data_purge_planned" if dry_run else "connector.data_purged",
        resource_type="connector",
        resource_id=connector_id,
        metadata={
            "vendor": vendor,
            "disconnected_at": str(disconnected_at),
            "hard_deleted": bool(payload.get("hard_deleted")),
            "event_id": str(event.get("event_id") or ""),
            "counts": counts,
        },
    )
    logger.info(
        "source_purge_%s org_id=%s connector_id=%s vendor=%s counts=%s",
        "planned" if dry_run else "done",
        org_id,
        connector_id,
        vendor,
        counts,
    )
    return counts


def register_source_lifecycle_handlers() -> None:
    """Register outbox consumers once per process (safe to call repeatedly)."""
    if any(r.name == PURGE_HANDLER_NAME for r in handlers_for(EVENT_SOURCE_DISCONNECTED)):
        return
    register_domain_event_handler(
        EVENT_SOURCE_DISCONNECTED,
        PURGE_HANDLER_NAME,
        lambda client, event: handle_source_disconnected(client, event),
    )


def _other_live_google_connector(client: Any, org_id: str, connector_id: str) -> bool:
    res = (
        client.table("connectors")
        .select("id, vendor, type")
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .execute()
    )
    for r in res.data or []:
        if str(r.get("id")) == connector_id:
            continue
        if canonical_vendor(r.get("vendor") or r.get("type")) in GOOGLE_FAMILY:
            return True
    return False


def revoke_on_disconnect(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    connector_id: str,
    vendor: str | None,
    config: dict[str, Any] | None = None,
) -> RevokeOutcome:
    """Revoke the provider grant before our stored tokens are dropped. Never raises."""
    if getattr(settings, "connector_provider_revoke_on_disconnect", False) is not True:
        return RevokeOutcome("disabled")
    v = canonical_vendor(vendor)
    try:
        from app.connectors.hubspot_oauth import load_oauth_tokens

        tokens = load_oauth_tokens(client, connector_id, settings)
        shared = v in GOOGLE_FAMILY and _other_live_google_connector(client, org_id, connector_id)
        return revoke_provider_tokens(v, tokens, config=config, shares_grant_with_live_connector=shared)
    except Exception as exc:  # noqa: BLE001
        logger.warning("provider_revoke_error vendor=%s error=%s", v, type(exc).__name__)
        return RevokeOutcome("failed", f"{v} {type(exc).__name__}")


# ---------------------------------------------------------------------------------------
# Deletion propagation (SOURCE_DELETION_PROPAGATION_ENABLED)
#
# Safety rules:
#   1. Absence is never proof. A record missing from a listing only nominates its
#      document; it is removed only when the provider itself says the record is gone
#      (archived, trashed, deleted, or 404 on a direct read by id).
#   2. A sweep nominates anything only when the caller proved it complete (every listing
#      well formed, pagination finished, no errors).
#   3. Safety cap: one reconcile or verification pass may remove at most
#      max(SAFETY_CAP_FLOOR, SAFETY_CAP_FRACTION x documents considered). Above that it
#      removes nothing, logs an error and writes a "refused" receipt: a real mass
#      deletion is an explicit purge, never a side effect of a sync.
#   4. Dry-run: while SOURCE_PURGE_DRY_RUN is anything but an explicit False (the same
#      switch and convention as the disconnect purge) removals are planned and recorded,
#      never executed.
#   5. Every pass that finds something writes an audit receipt (planned, done, refused),
#      the same audit trail the disconnect purge writes.
# ---------------------------------------------------------------------------------------

SAFETY_CAP_FRACTION = 0.25
SAFETY_CAP_FLOOR = 5
MAX_RECONCILE_VERIFICATIONS = 200
DOCUMENT_PAGE_SIZE = 1000
# Ingest jobs cancelled because their record was removed upstream. The status stays within
# the existing CHECK constraint (queued/running/completed/failed); the error code marks it.
SOURCE_DELETED_ERROR_CODE = "source_deleted"
_AUDIT_ID_SAMPLE = 50


def deletion_propagation_enabled(settings: Any) -> bool:
    return getattr(settings, "source_deletion_propagation_enabled", False) is True


def deletion_dry_run(settings: Any) -> bool:
    """Anything but an explicit False keeps deletion propagation a plan."""
    return getattr(settings, "source_purge_dry_run", True) is not False


def within_safety_cap(considered: int, removing: int) -> bool:
    if removing <= SAFETY_CAP_FLOOR:
        return True
    return considered > 0 and removing <= considered * SAFETY_CAP_FRACTION


def _record(
    client: Any,
    *,
    org_id: str,
    source_id: str,
    action: str,
    signal: str,
    metadata: dict[str, Any],
) -> None:
    from app.workflows.audit import write_audit_event

    try:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=SYSTEM_ACTOR,
            action=action,
            resource_type="rag_source",
            resource_id=source_id,
            metadata={"signal": signal, **metadata},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("source_documents_audit_failed action=%s error=%s", action, type(exc).__name__)


def list_source_documents(
    client: Any, *, org_id: str, source_id: str, external_id_prefix: str
) -> list[dict[str, Any]]:
    """Every document of one source under ``prefix``, paged (PostgREST caps one read)."""
    out: list[dict[str, Any]] = []
    start = 0
    while True:
        res = (
            client.table("rag_documents")
            .select("id, external_id")
            .eq("org_id", org_id)
            .eq("source_id", source_id)
            .like("external_id", f"{external_id_prefix}%")
            .order("id")
            .range(start, start + DOCUMENT_PAGE_SIZE - 1)
            .execute()
        )
        rows = [r for r in (res.data or []) if isinstance(r, dict) and r.get("id")]
        out.extend(rows)
        if len(rows) < DOCUMENT_PAGE_SIZE:
            return out
        start += DOCUMENT_PAGE_SIZE


def _select_in(
    client: Any,
    table: str,
    *,
    org_id: str,
    source_id: str,
    values: list[str],
    statuses: list[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(0, len(values), 100):
        q = (
            client.table(table)
            .select("id, external_id")
            .eq("org_id", org_id)
            .eq("source_id", source_id)
            .in_("external_id", values[i : i + 100])
        )
        if statuses:
            q = q.in_("status", statuses)
        rows.extend(r for r in (q.execute().data or []) if isinstance(r, dict))
    return rows


def _cancel_ingest_jobs(client: Any, *, org_id: str, source_id: str, job_ids: list[str]) -> None:
    """Fail queued/running ingest jobs of removed records and drop their raw payloads.

    The worker re-reads this marker after activating a version and discards that version,
    so a job claimed before the cancel cannot bring the document back.
    """
    now = datetime.now(UTC).isoformat()
    for i in range(0, len(job_ids), 100):
        client.table("rag_ingest_jobs").update(
            {
                "status": "failed",
                "error_code": SOURCE_DELETED_ERROR_CODE,
                "request_payload": None,
                "completed_at": now,
                "updated_at": now,
                "worker_id": None,
                "heartbeat_at": None,
            }
        ).eq("org_id", org_id).eq("source_id", source_id).in_("id", job_ids[i : i + 100]).in_(
            "status", ["queued", "running"]
        ).execute()


def _remove_observations(client: Any, *, org_id: str, external_ids: list[str]) -> None:
    """Delete observations derived from the removed records (``system:type:id`` ids)."""
    groups: dict[tuple[str, str], list[str]] = {}
    for ext in external_ids:
        parts = ext.split(":", 2)
        if len(parts) == 3 and all(parts):
            groups.setdefault((parts[0], parts[1]), []).append(parts[2])
    for (system, record_type), ids in groups.items():
        try:
            for i in range(0, len(ids), 100):
                client.table("entity_observations").delete().eq("org_id", org_id).eq(
                    "source_system", system
                ).eq("source_record_type", record_type).in_("source_record_id", ids[i : i + 100]).execute()
        except Exception as exc:  # noqa: BLE001
            # The table is optional (Phase 3 migration); a failure never blocks the removal.
            logger.warning(
                "source_observations_removal_failed org_id=%s system=%s error=%s",
                org_id,
                system,
                type(exc).__name__,
            )


def remove_source_documents(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    source_id: str,
    external_ids: set[str] | list[str],
    signal: str = "provider_flag",
) -> int:
    """Remove the named records of one source after the provider reported them removed.

    Pass only ids the provider explicitly flagged (deleted, archived, trashed, 404 by id),
    never ids merely absent from a page. Besides the documents (chunks and embeddings
    cascade) this fails the records' queued/running ingest jobs and clears their raw
    payloads, so a queued job cannot resurrect a deleted record, and deletes observations
    derived from them. Honours dry-run and writes an audit receipt. Returns the number of
    documents removed (0 in dry-run).
    """
    if not deletion_propagation_enabled(settings):
        return 0
    wanted = sorted({str(e) for e in external_ids if e})
    if not org_id or not source_id or not wanted:
        return 0
    dry_run = deletion_dry_run(settings)
    jobs = _select_in(
        client, "rag_ingest_jobs", org_id=org_id, source_id=source_id, values=wanted, statuses=["queued", "running"]
    )
    job_ids = sorted({str(j["id"]) for j in jobs if j.get("id")})
    if job_ids and not dry_run:
        # Before the document read: a job that activates after this sees the marker and
        # discards its version; one that activated before is in the read below.
        _cancel_ingest_jobs(client, org_id=org_id, source_id=source_id, job_ids=job_ids)
    docs = _select_in(client, "rag_documents", org_id=org_id, source_id=source_id, values=wanted)
    doc_ids = sorted({str(d["id"]) for d in docs if d.get("id")})
    if not doc_ids and not job_ids:
        return 0
    meta = {
        "flagged": len(wanted),
        "documents": len(doc_ids),
        "ingest_jobs": len(job_ids),
        "dry_run": dry_run,
        "external_ids": wanted[:_AUDIT_ID_SAMPLE],
    }
    if dry_run:
        _record(
            client,
            org_id=org_id,
            source_id=source_id,
            action="source.documents_removal_planned",
            signal=signal,
            metadata=meta,
        )
        logger.info(
            "source_documents_removal_planned org_id=%s source_id=%s signal=%s documents=%s jobs=%s",
            org_id,
            source_id,
            signal,
            len(doc_ids),
            len(job_ids),
        )
        return 0
    removed = _delete_documents(client, org_id=org_id, source_id=source_id, document_ids=doc_ids)
    _remove_observations(client, org_id=org_id, external_ids=wanted)
    _record(client, org_id=org_id, source_id=source_id, action="source.documents_removed", signal=signal, metadata=meta)
    logger.info(
        "source_documents_removed_upstream org_id=%s source_id=%s signal=%s flagged=%s removed=%s jobs_cancelled=%s",
        org_id,
        source_id,
        signal,
        len(wanted),
        removed,
        len(job_ids),
    )
    return removed


def _refuse(
    client: Any,
    *,
    org_id: str,
    source_id: str,
    signal: str,
    considered: int,
    gone: list[str],
    errors: list[str] | None,
) -> None:
    logger.error(
        "source_documents_removal_refused org_id=%s source_id=%s signal=%s considered=%s removing=%s",
        org_id,
        source_id,
        signal,
        considered,
        len(gone),
    )
    _record(
        client,
        org_id=org_id,
        source_id=source_id,
        action="source.documents_removal_refused",
        signal=signal,
        metadata={"considered": considered, "documents": len(gone), "external_ids": sorted(gone)[:_AUDIT_ID_SAMPLE]},
    )
    if errors is not None:
        errors.append(
            f"{signal}: refused to remove {len(gone)} of {considered} documents in one pass "
            f"(safety cap: {SAFETY_CAP_FLOOR} or {int(SAFETY_CAP_FRACTION * 100)}%); purge explicitly if intended"
        )


def reconcile_source_documents(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    source_id: str,
    external_id_prefix: str,
    seen_external_ids: set[str],
    is_gone: Callable[[str], bool],
    sweep_complete: bool,
    max_verifications: int = MAX_RECONCILE_VERIFICATIONS,
    position: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    signal: str = "full_sweep",
) -> int:
    """Remove documents a complete sweep did not see AND the provider confirms are gone.

    ``sweep_complete`` must be True only when every listing of the sweep was well formed
    and fully paginated, with no errors; otherwise nothing is nominated. Each unseen
    document is then checked by id with ``is_gone(external_id)``: True when the provider
    says it is deleted/archived/trashed/404; False when it still exists (for example a
    target removed from the sync config: out of scope, kept for an explicit purge);
    raising means unknown and keeps it. At most ``max_verifications`` are checked per
    pass, rotating through ``position["after"]`` so every candidate is reached over
    several passes. The safety cap applies to the source's documents under ``prefix``.
    Returns the number of documents removed.
    """
    if not deletion_propagation_enabled(settings) or not external_id_prefix:
        return 0
    if sweep_complete is not True:
        logger.warning(
            "source_reconcile_skipped_incomplete_sweep org_id=%s source_id=%s prefix=%s",
            org_id,
            source_id,
            external_id_prefix,
        )
        return 0
    docs = list_source_documents(client, org_id=org_id, source_id=source_id, external_id_prefix=external_id_prefix)
    total = len(docs)
    candidates = sorted({str(d.get("external_id") or "") for d in docs} - set(seen_external_ids) - {""})
    if not candidates:
        if position is not None:
            position.pop("after", None)
        return 0
    after = str((position or {}).get("after") or "")
    start = next((i for i, c in enumerate(candidates) if c > after), len(candidates)) if after else 0
    batch = (candidates[start:] + candidates[:start])[: max(int(max_verifications), 0)]
    gone: list[str] = []
    kept = 0
    for ext in batch:
        try:
            if is_gone(ext):
                gone.append(ext)
            else:
                kept += 1
        except Exception as exc:  # noqa: BLE001
            kept += 1
            if errors is not None:
                errors.append(f"{signal} verify {ext}: {type(exc).__name__}: {exc}")
    if position is not None:
        if batch and len(batch) < len(candidates):
            position["after"] = batch[-1]
        else:
            position.pop("after", None)
    if kept:
        logger.info(
            "source_reconcile_kept_unseen org_id=%s source_id=%s kept=%s",
            org_id,
            source_id,
            kept,
        )
    if not gone:
        return 0
    if not within_safety_cap(total, len(gone)):
        _refuse(client, org_id=org_id, source_id=source_id, signal=signal, considered=total, gone=gone, errors=errors)
        return 0
    return remove_source_documents(
        client, settings, org_id=org_id, source_id=source_id, external_ids=gone, signal=signal
    )


def verify_source_documents(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    source_id: str,
    external_id_prefix: str,
    is_gone: Callable[[str], bool],
    position: dict[str, Any],
    batch_size: int,
    errors: list[str],
    signal: str = "verify_by_id",
) -> int:
    """Rotating check-by-id of indexed documents, for deletions no listing reports.

    Some deletions never appear in a provider listing (HubSpot GDPR/permanent deletes,
    Zendesk tickets purged from the deleted-tickets list, Confluence pages purged from
    the trash). Each pass reads ``batch_size`` documents after ``position["after"]``
    (ordered by external_id) and asks the provider for each by id; ``is_gone`` returns
    True only on an explicit signal (404 / archived / trashed). The position wraps, so
    every indexed document is checked once per cycle. A provider error stops the pass at
    that document (the position stays before it); the safety cap applies per batch.
    """
    if not deletion_propagation_enabled(settings) or batch_size <= 0:
        return 0
    after = position.get("after")
    q = (
        client.table("rag_documents")
        .select("id, external_id")
        .eq("org_id", org_id)
        .eq("source_id", source_id)
        .like("external_id", f"{external_id_prefix}%")
    )
    if after:
        q = q.gt("external_id", str(after))
    rows = q.order("external_id").limit(batch_size).execute().data or []
    ext_ids: list[str] = []
    for r in rows:
        ext = str(r.get("external_id") or "") if isinstance(r, dict) else ""
        if ext and ext not in ext_ids:
            ext_ids.append(ext)
    gone: list[str] = []
    checked: list[str] = []
    for ext in ext_ids:
        try:
            if is_gone(ext):
                gone.append(ext)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{signal} {ext}: {type(exc).__name__}: {exc}")
            break
        checked.append(ext)
    if gone and not within_safety_cap(len(checked), len(gone)):
        # Too many at once to be a normal deletion rate: keep the position, delete nothing.
        _refuse(
            client, org_id=org_id, source_id=source_id, signal=signal, considered=len(checked), gone=gone, errors=errors
        )
        return 0
    removed = 0
    if gone:
        removed = remove_source_documents(
            client, settings, org_id=org_id, source_id=source_id, external_ids=gone, signal=signal
        )
    if len(checked) < len(ext_ids):
        if checked:
            position["after"] = checked[-1]
    elif len(rows) < batch_size:
        position.pop("after", None)  # reached the end of the source: wrap
    elif checked:
        position["after"] = checked[-1]
    return removed


def _delete_documents(client: Any, *, org_id: str, source_id: str, document_ids: list[str]) -> int:
    """Delete ``rag_documents`` rows by id, always scoped to the org and source."""
    removed = 0
    for i in range(0, len(document_ids), 100):
        chunk = document_ids[i : i + 100]
        client.table("rag_documents").delete().eq("org_id", org_id).eq("source_id", source_id).in_(
            "id", chunk
        ).execute()
        removed += len(chunk)
    return removed


def ingest_job_cancelled(client: Any, job_id: str) -> bool:
    """True when deletion propagation failed this ingest job after it was claimed."""
    try:
        res = client.table("rag_ingest_jobs").select("status, error_code").eq("id", job_id).limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag_ingest_cancel_check_failed job_id=%s error=%s", job_id, type(exc).__name__)
        return False
    rows = res.data if isinstance(res.data, list) else []
    return bool(rows) and isinstance(rows[0], dict) and rows[0].get("error_code") == SOURCE_DELETED_ERROR_CODE
