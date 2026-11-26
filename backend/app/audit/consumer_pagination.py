"""Read-only, tenant-scoped audit consumer scans.

Stable UUID keyset traversal avoids offset shifts and short-page assumptions:
PostgREST may impose a row limit smaller than the requested page. No store
fallback, union or deduplication across distinct compliance/operational stores.
A scan is not a transaction snapshot; concurrent retention/inserts can change
its contents. Fail rather than silently return a partial scan on invalid data
or a resource limit.
"""
from __future__ import annotations

from uuid import UUID

_PAGE_SIZE = 500
_MAX_ROWS = 100_000


def scan_audit_rows(client, store, org_id, *, columns="*", since=None, until=None, actions=None):
    if store not in {"audit_logs", "audit_events"} or not org_id:
        raise ValueError("Tenant-scoped audit store required")
    projection = columns if columns == "*" else "id,org_id," + columns
    cursor = None
    rows = []
    while True:
        query = client.table(store).select(projection).eq("org_id", org_id)
        if since is not None:
            query = query.gte("created_at", since)
        if until is not None:
            query = query.lte("created_at", until)
        if actions is not None:
            query = query.in_("action", actions)
        if cursor is not None:
            query = query.gt("id", str(cursor))
        page = query.order("id").limit(_PAGE_SIZE).execute().data
        if not isinstance(page, list):
            raise RuntimeError("Invalid audit page")
        if not page:
            return rows
        for row in page:
            if not isinstance(row, dict) or str(row.get("org_id")) != str(org_id):
                raise RuntimeError("Audit page outside tenant scope")
            try:
                identity = UUID(str(row["id"]))
            except (KeyError, ValueError, TypeError, AttributeError) as exc:
                raise RuntimeError("Invalid audit identity") from exc
            if cursor is not None and identity <= cursor:
                raise RuntimeError("Audit pagination did not advance")
            cursor = identity
            rows.append(row)
            if len(rows) > _MAX_ROWS:
                raise RuntimeError("Audit scan exceeds safe synchronous limit; narrow the time window")
