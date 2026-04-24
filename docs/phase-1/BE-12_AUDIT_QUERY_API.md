# BE-12 — Audit Query API (Read-Only)

**Authority:** SYSTEM.md, MASTER_PHASED_MODULE_PLAN.md, BE-11 (audit_events table).  
**Scope:** Secure, org-scoped, read-only API for querying audit events. No new tables; no writes.

---

## Endpoint

**GET /api/audit**

### Query parameters

| Parameter       | Type   | Required | Description |
|----------------|--------|----------|-------------|
| resource_type  | string | Yes      | e.g. `workflow_run` |
| resource_id    | string | Yes      | UUID of the resource |
| limit          | int    | No       | Page size; default 50, max 200 |
| cursor         | string | No       | Opaque cursor for next page (from previous response) |
| action_prefix  | string | No       | Filter actions that start with this prefix, e.g. `workflow.dry_run.` |

### Response (200)

```json
{
  "items": [
    {
      "id": "uuid",
      "action": "workflow.dry_run.started",
      "actor_id": "uuid",
      "resource_type": "workflow_run",
      "resource_id": "uuid",
      "metadata": { "run_type": "dry_run" },
      "created_at": "2025-02-04T12:00:00Z"
    }
  ],
  "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNS0wMi0wNFQxMjowMDowMFoiLCJpZCI6InV1aWQifQ"
}
```

- **items:** Audit events for the given resource, ordered by `created_at DESC`, then `id DESC`.
- **next_cursor:** Present when there are more results; pass as `cursor` on the next request. Absent when no further pages.

### Cursor format

Cursor is a base64url-encoded JSON object: `{ "created_at": "<iso>", "id": "<uuid>" }`.  
Pagination uses **seek**: the next page returns rows where `(created_at, id) < (cursor.created_at, cursor.id)`.

### Errors

| Status | Condition |
|--------|-----------|
| 400 | Missing `resource_type` or `resource_id`; `resource_id` not a valid UUID; `limit` out of range |
| 401 | Missing or invalid JWT |
| 403 | Valid auth but no org context |

### Security

- Auth required (BE-00). Org is derived from auth context only (not from request body or query).
- All queries are filtered by `org_id`; users only see events for their org.
- Do not log tokens, query text, or PII. Log only: request_id, org_id, resource_type, resource_id, item_count, latency_ms.

---

## Examples

### First page (workflow run events)

```http
GET /api/audit?resource_type=workflow_run&resource_id=550e8400-e29b-41d4-a716-446655440000&limit=50
Authorization: Bearer <jwt>
```

### Next page

```http
GET /api/audit?resource_type=workflow_run&resource_id=550e8400-e29b-41d4-a716-446655440000&limit=50&cursor=eyJjcmVhdGVkX2F0IjoiMjAyNS0wMi0wNFQxMjowMDowMFoiLCJpZCI6InV1aWQifQ
Authorization: Bearer <jwt>
```

### Only dry-run actions

```http
GET /api/audit?resource_type=workflow_run&resource_id=550e8400-e29b-41d4-a716-446655440000&action_prefix=workflow.dry_run.
Authorization: Bearer <jwt>
```

---

## Implementation notes

- **DB:** Uses existing `audit_events` table (BE-11). Query is implemented via Postgres function `audit_query` (migration `20250204000005_audit_query_function.sql`) for correct seek pagination.
- **Router:** `backend/app/routers/audit.py`.
- **Query helper:** `backend/app/audit/query.py` (cursor encode/decode, RPC call).
- No writes to audit_events in BE-12; write path remains internal (e.g. BE-11 dry-run).
