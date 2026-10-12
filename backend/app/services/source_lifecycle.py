"""Phase 2B source lifecycle: what happens to a source's data when it goes away.

Three pieces, each off until switched on:

* ``revoke_on_disconnect`` runs inside the disconnect request, before our copy of the
  tokens is dropped, and asks the provider to revoke the grant
  (CONNECTOR_PROVIDER_REVOKE_ON_DISCONNECT).
* ``handle_source_disconnected`` consumes the ``source.disconnected`` outbox event and
  removes the data derived from that connector in one database transaction
  (``purge_connector_derived_data``). It writes a dry-run receipt only, until
  SOURCE_PURGE_DRY_RUN=false. Runs only when the relay is on.
* ``reconcile_source_documents`` removes indexed documents a full-sweep sync no longer
  finds upstream (SOURCE_DELETION_PROPAGATION_ENABLED).
"""
from __future__ import annotations

import re
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


def reconcile_source_documents(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    source_id: str,
    external_id_prefix: str,
    seen_external_ids: set[str],
) -> int:
    """Delete documents under ``prefix`` that the last complete sweep did not see.

    Callers must pass only sweeps that finished without errors; a partial sweep
    would otherwise delete documents that still exist upstream. Returns the
    number of documents removed (chunks and embeddings cascade).
    """
    if getattr(settings, "source_deletion_propagation_enabled", False) is not True or not external_id_prefix:
        return 0
    res = (
        client.table("rag_documents")
        .select("id, external_id")
        .eq("org_id", org_id)
        .eq("source_id", source_id)
        .like("external_id", f"{external_id_prefix}%")
        .execute()
    )
    stale = [
        str(r["id"])
        for r in (res.data or [])
        if r.get("id") and str(r.get("external_id") or "") not in seen_external_ids
    ]
    removed = 0
    for i in range(0, len(stale), 100):
        chunk = stale[i : i + 100]
        client.table("rag_documents").delete().eq("org_id", org_id).eq("source_id", source_id).in_(
            "id", chunk
        ).execute()
        removed += len(chunk)
    if removed:
        logger.info(
            "source_documents_reconciled org_id=%s source_id=%s removed=%s", org_id, source_id, removed
        )
    return removed
