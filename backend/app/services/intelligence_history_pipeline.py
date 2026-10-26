"""Tenant-scoped, resumable historical ingest and deterministic identity matching.

Adapters are injectable and must implement fetch_page(cursor, limit). This module
never acquires provider credentials or bypasses connector authorization. A caller
must validate the connector's org, read scopes and user-granted sync policy.
"""
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

MAX_PAGE_SIZE = 100
MAX_PAGES_PER_RUN = 25
MAX_RECORD_BYTES = 64_000
ALLOWED_TYPES = frozenset({"contact", "company", "ticket", "deal", "invoice"})
ALLOWED_PROVIDERS = frozenset({"hubspot", "zendesk", "salesforce", "stripe"})


class HistoryAdapter(Protocol):
    def fetch_page(self, object_type: str, cursor: dict[str, Any], limit: int) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Source:
    org_id: str
    connector_id: str
    provider: str
    object_type: str


def _validate(source: Source) -> None:
    if not source.org_id or not source.connector_id:
        raise ValueError("Tenant and connector identifiers required")
    if source.provider not in ALLOWED_PROVIDERS or source.object_type not in ALLOWED_TYPES:
        raise ValueError("Unsupported historical provider or record type")


def _normalize_identity(data: dict[str, Any]) -> dict[str, str]:
    email = str(data.get("email") or "").strip().lower()
    domain = str(data.get("domain") or "").strip().lower().removeprefix("www.")
    output: dict[str, str] = {}
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        output["email"] = email
    if re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.[a-z]{2,}", domain) and ".." not in domain:
        output["domain"] = domain
    return output


def _fingerprint(kind: str, value: str) -> str:
    return hashlib.sha256((kind + ":" + value).encode("utf-8")).hexdigest()


def match_observations(rows: list[dict[str, Any]], *, org_id: str) -> list[dict[str, Any]]:
    """Join only exact normalized keys; conflicts remain candidates, never automatic merges."""
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        if row.get("org_id") != org_id:
            continue
        identity = row.get("normalized_identity") or {}
        for kind in ("email", "domain"):
            value = identity.get(kind)
            if not isinstance(value, str) or not value:
                continue
            ref = {"connector_id": str(row["connector_id"]),
                   "object_type": str(row["object_type"]),
                   "external_id": str(row["external_id"])}
            groups.setdefault((kind, _fingerprint(kind, value)), []).append(ref)
    matches = []
    for (kind, digest), refs in groups.items():
        distinct = list({(r["connector_id"], r["object_type"], r["external_id"]): r
                         for r in refs}.values())
        providers = {r["connector_id"] for r in distinct}
        if len(providers) < 2:
            continue
        matches.append({"org_id": org_id, "identity_kind": kind, "identity_hash": digest,
                        "match_status": "candidate" if kind == "domain" else "verified_key",
                        "record_references": sorted(distinct, key=lambda r: (
                            r["connector_id"], r["object_type"], r["external_id"]))})
    return matches


def ingest_history(
    db: Any, source: Source, adapter: HistoryAdapter, *,
    max_pages: int = MAX_PAGES_PER_RUN, page_size: int = MAX_PAGE_SIZE,
) -> dict[str, Any]:
    """Idempotent upserts and page-level checkpoints for crash-safe resumption.

    Call ONLY after permission/read-scope checks. If a page fails, its cursor is
    not advanced. Provider changes between pages may duplicate rows safely.
    """
    _validate(source)
    if not 1 <= page_size <= MAX_PAGE_SIZE or not 1 <= max_pages <= MAX_PAGES_PER_RUN:
        raise ValueError("Ingestion bounds exceeded")
    key = {"org_id": source.org_id, "connector_id": source.connector_id,
           "object_type": source.object_type}
    row = (db.table("intelligence_history_checkpoints").select("cursor")
           .eq("org_id", source.org_id).eq("connector_id", source.connector_id)
           .eq("object_type", source.object_type).limit(1).execute())
    cursor = (row.data or [{}])[0].get("cursor") or {}
    count = 0
    done = False
    for _ in range(max_pages):
        page = adapter.fetch_page(source.object_type, cursor, page_size)
        records = page.get("records")
        if not isinstance(records, list) or len(records) > page_size:
            raise ValueError("Invalid provider page")
        clean = []
        now = datetime.now(timezone.utc).isoformat()
        for item in records:
            if not isinstance(item, dict) or not str(item.get("id") or "").strip():
                raise ValueError("Provider row is missing a stable external ID")
            import json
            if len(json.dumps(item, default=str).encode("utf-8")) > MAX_RECORD_BYTES:
                raise ValueError("Provider row exceeds allowed size")
            clean.append({**key, "provider": source.provider,
                          "external_id": str(item["id"]),
                          "observed_at": now,
                          "source_updated_at": item.get("updated_at"),
                          "record": item,
                          "normalized_identity": _normalize_identity(item)})
        if clean:
            db.table("intelligence_history_records").upsert(
                clean, on_conflict="org_id,connector_id,object_type,external_id").execute()
            count += len(clean)
        next_cursor = page.get("next_cursor")
        done = next_cursor is None
        # A checkpoint only follows a successful records upsert.
        if not done and (not isinstance(next_cursor, dict) or next_cursor == cursor):
            raise ValueError("Non-advancing provider cursor")
        cursor = {} if done else next_cursor
        db.table("intelligence_history_checkpoints").upsert(
            {**key, "provider": source.provider, "cursor": cursor,
             "state": "complete" if done else "running",
             "completed_at": now if done else None,
             "updated_at": now},
            on_conflict="org_id,connector_id,object_type").execute()
        if done:
            break
    return {"org_id": source.org_id, "connector_id": source.connector_id,
            "object_type": source.object_type, "records_synced": count,
            "complete": done, "requires_more_pages": not done}


def save_matches(db: Any, org_id: str, records: list[dict[str, Any]]) -> int:
    matches = match_observations(records, org_id=org_id)
    if matches:
        db.table("intelligence_entity_matches").upsert(
            matches, on_conflict="org_id,identity_kind,identity_hash").execute()
    return len(matches)


def run_authorized_history_batch(
    db: Any, org_id: str, connectors: list[dict[str, Any]],
    adapters: dict[str, HistoryAdapter], permitted: Any,
    *, max_pages: int = MAX_PAGES_PER_RUN,
) -> dict[str, Any]:
    """Gate and run provider backfills, then match persisted org observations.

    `permitted(connector, object_type)` MUST verify org ownership, active
    connector status, user-authorized read scopes and connector sync policy.
    Missing authorization is a hard skip. Provider adapters are injected by the
    connector integration layer and never instantiated from untrusted inputs.
    """
    from app.services.intelligence_history_adapters import authorized_history_object
    receipts = []
    for connector in connectors[:20]:
        if connector.get("org_id") != org_id or connector.get("status") != "active":
            continue
        vendor = str(connector.get("type") or "").lower()
        adapter = adapters.get(str(connector.get("id") or ""))
        if vendor not in ALLOWED_PROVIDERS or adapter is None:
            continue
        for object_type in sorted(ALLOWED_TYPES):
            if not authorized_history_object(connector, object_type) or not permitted(connector, object_type):
                continue
            source = Source(org_id, str(connector["id"]), vendor, object_type)
            try:
                receipts.append(ingest_history(db, source, adapter, max_pages=max_pages))
            except Exception:
                receipts.append({"connector_id": source.connector_id,
                                 "object_type": object_type, "complete": False,
                                 "error_code": "provider_sync_failed"})
    # Read back persisted, org-scoped records. Never match a provider payload
    # that hasn't been committed to the tenant partition.
    response = (db.table("intelligence_history_records")
                .select("org_id,connector_id,object_type,external_id,normalized_identity")
                .eq("org_id", org_id).limit(2000).execute())
    observations = list(response.data or [])
    truncated = len(observations) >= 2000
    # Refuse to publish incomplete identity groups when the bounded read cannot
    # cover the full history. A paginated identity-index rebuild is required.
    matched = 0 if truncated else save_matches(db, org_id, observations)
    return {"org_id": org_id, "receipts": receipts, "match_groups": matched,
            "truncated_match_input": truncated}
