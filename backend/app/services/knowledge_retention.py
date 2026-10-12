"""Phase 2C retention: drop indexed documents older than the org's per-vendor limit.

Reads ``retentionDays`` from the source governance policy. A document's age is
its ``updated_at`` (a resync refreshes it), so retention removes only what the
source has not sent again within the window. Chunks, embeddings and ingest jobs
cascade from rag_documents.

Off unless KNOWLEDGE_RETENTION_PRUNE_ENABLED is true.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.services.source_governance import SETTINGS_KEY, normalize_source_governance

logger = get_logger(__name__)

DELETE_BATCH = 200
MAX_DOCUMENTS_PER_SOURCE_RUN = 5000


def _orgs_with_retention(client: Any) -> list[tuple[str, dict[str, int]]]:
    res = (
        client.table("organizations")
        .select("id, settings")
        .not_.is_(f"settings->{SETTINGS_KEY}->retentionDays", "null")
        .execute()
    )
    out: list[tuple[str, dict[str, int]]] = []
    for row in res.data or []:
        settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
        policy = normalize_source_governance(settings.get(SETTINGS_KEY))
        if policy["retentionDays"]:
            out.append((str(row["id"]), policy["retentionDays"]))
    return out


def prune_org_expired_documents(
    client: Any,
    org_id: str,
    retention_days: dict[str, int],
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Delete expired documents per vendor for one org. Returns removed counts by vendor."""
    now = now or datetime.now(UTC)
    removed: dict[str, int] = {}
    for vendor, days in sorted(retention_days.items()):
        cutoff = (now - timedelta(days=int(days))).isoformat()
        sources = (
            client.table("rag_sources").select("id").eq("org_id", org_id).eq("type", vendor).execute()
        )
        total = 0
        for src in sources.data or []:
            sid = str(src.get("id") or "")
            if not sid:
                continue
            docs = (
                client.table("rag_documents")
                .select("id")
                .eq("org_id", org_id)
                .eq("source_id", sid)
                .lt("updated_at", cutoff)
                .limit(MAX_DOCUMENTS_PER_SOURCE_RUN)
                .execute()
            )
            ids = [str(d["id"]) for d in (docs.data or []) if d.get("id")]
            for i in range(0, len(ids), DELETE_BATCH):
                batch = ids[i : i + DELETE_BATCH]
                client.table("rag_documents").delete().eq("org_id", org_id).eq("source_id", sid).in_(
                    "id", batch
                ).execute()
            total += len(ids)
        if total:
            removed[vendor] = total
    return removed


def run_retention_prune(client: Any) -> dict[str, dict[str, int]]:
    """One pass across all orgs that set retention. Never raises per org."""
    results: dict[str, dict[str, int]] = {}
    for org_id, retention in _orgs_with_retention(client):
        try:
            removed = prune_org_expired_documents(client, org_id, retention)
        except Exception as exc:  # noqa: BLE001
            logger.warning("knowledge_retention_prune_failed org_id=%s error=%s", org_id, exc)
            continue
        if removed:
            results[org_id] = removed
            from app.workflows.audit import write_audit_event

            write_audit_event(
                client,
                org_id=org_id,
                actor_id="system:knowledge_retention",
                action="knowledge.retention_pruned",
                resource_type="org_settings",
                resource_id=org_id,
                metadata={"removed": removed, "retentionDays": retention},
            )
            logger.info("knowledge_retention_pruned org_id=%s removed=%s", org_id, removed)
    return results
