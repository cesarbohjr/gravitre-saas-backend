# Connected files — data handling and retention decision

**Decision date:** 2026-07-21  
**Scope:** Read-only access to files in connected vendor systems (Google Drive, SharePoint/OneDrive, Slack files, Notion pages, Confluence pages).

## Decision

Fetched connected-file content is **not** persisted in Gravitre storage (`rag_documents`, Supabase Storage, or any durable org datastore).

| Layer | Retention | Rationale |
|-------|-----------|-----------|
| Vendor fetch (`get_file_content`) | Live API call every invocation | Permissions enforced at query time; revoked access cannot leak via cache |
| In-process transient cache | **60 seconds**, keyed by org + vendor + file_id | Performance only within a single response/turn; not shared across users as permission truth |
| Read-action result cache (90s) | **Disabled** for `search_files`, `get_file_content`, and related actions | Same permission requirement as above |
| RAG index (`rag_chunks` / embeddings) | **Not used** for connected-file query-time reads | Avoids new permanent storage category; distinct from admin upload / Notion-Confluence sync pipelines |
| Module B parameter ledger | Stores **metadata only** (file_id, name, vendor, web_link, ordered refs JSON) | Enables follow-up turns without storing file bytes |

## Large / unsupported files

- **Size limit:** 10 MiB raw bytes per fetch; 500k characters extracted text.
- **Behavior:** Returns explicit error (`file_too_large`, `unsupported_file_type`) — no silent truncation except when `partial=True` is explicitly requested internally (not exposed to chat by default).
- **Oversized spreadsheets:** User sees an honest message to narrow scope or export a smaller range.

## Governance

This path **does not** introduce a new permanent customer-file storage category. No STA-312-style sign-off is required for the default design.

If product later requires durable indexing of connected files, that requires an explicit governance decision (owner + written option) before writing to `rag_documents` or object storage.

## Implementation references

- `backend/app/services/connected_files_service.py` — transient cache + extract/chunk via existing `file_extract` / `chunk_document_text`
- `backend/app/services/read_action_result_cache.py` — permission-sensitive action bypass
- `backend/app/services/parameter_ledger.py` — `ingest_connected_file_hits`, ordinal resolution
