# Confluence OAuth + RAG sync (STA-44)

Sync Confluence spaces into department-scoped RAG sources (CS/Sales/HR SOPs).

## Platform setup (operator)

1. Use the same [Atlassian 3LO app](https://developer.atlassian.com/cloud/confluence/oauth-2-3lo-apps/) as Jira, or create a dedicated app.
2. Add Confluence scopes: `read:confluence-content.all`, `read:confluence-space.summary`, `offline_access`.
3. **Redirect URI:**

```text
{API_PUBLIC_URL}/api/connectors/oauth/confluence/callback
```

4. Env on API host (falls back to `JIRA_CLIENT_*` when Confluence-specific vars are unset):

```env
JIRA_CLIENT_ID=
JIRA_CLIENT_SECRET=
# Optional overrides:
# CONFLUENCE_CLIENT_ID=
# CONFLUENCE_CLIENT_SECRET=
CONNECTOR_SECRETS_ENCRYPTION_KEY=...
API_PUBLIC_URL=https://gravitre-saas-backend-production.up.railway.app
```

## Customer flow

1. **Connectors → Connect Confluence** (OAuth).
2. Search and select sync targets (spaces).
3. **Run sync** to queue RAG ingest jobs.

## Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/connectors/{id}/confluence-sync` | Targets, `last_synced_at`, `stale` (>24h) |
| PUT | `/api/connectors/{id}/confluence-sync` | Set `targets`, optional `departmentId` |
| GET | `/api/connectors/{id}/confluence-sync/search?q=` | List/search spaces |
| POST | `/api/connectors/{id}/confluence-sync/run` | Queue ingest jobs |

### Example: configure targets

```json
PUT /api/connectors/{connector_id}/confluence-sync
{
  "targets": [
    { "id": "space-uuid", "type": "space", "title": "Customer Success SOPs", "key": "CS" }
  ],
  "departmentId": "optional-dept-uuid"
}
```

## RAG pipeline

Each page is ingested via `rag_ingest_jobs` with `external_id` `confluence:page:{id}`. Requires the ingest worker and `OPENAI_API_KEY` for embeddings.

## Scheduled sync (STA-45)

When sync targets are configured, the knowledge sync scheduler runs on `connector.sync_frequency` (default `1h` on create). See [KNOWLEDGE_SYNC.md](./KNOWLEDGE_SYNC.md).

## Code

- `backend/app/connectors/confluence_oauth.py`
- `backend/app/connectors/confluence.py`
- `backend/app/services/confluence_sync_service.py`
- `backend/app/routers/confluence_sync.py`

## Related

- [NOTION.md](./NOTION.md)
- [KNOWLEDGE_SYNC.md](./KNOWLEDGE_SYNC.md)
- [JIRA.md](./JIRA.md)
