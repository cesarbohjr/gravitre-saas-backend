# Notion OAuth + RAG sync (STA-43)

Sync Notion pages and databases into department-scoped RAG sources.

## Platform setup (operator)

1. Create a [Notion integration](https://www.notion.so/my-integrations) with OAuth enabled.
2. **Redirect URI:**

```text
{API_PUBLIC_URL}/api/connectors/oauth/notion/callback
```

3. Env on API host:

```env
NOTION_CLIENT_ID=
NOTION_CLIENT_SECRET=
CONNECTOR_SECRETS_ENCRYPTION_KEY=...
API_PUBLIC_URL=https://gravitre-saas-backend-production.up.railway.app
```

4. Share pages/databases with the integration in Notion after connect.

## Customer flow

1. **Connectors → Connect Notion** (OAuth).
2. Search and select sync targets (pages or databases).
3. **Run sync** to queue RAG ingest jobs.

## Admin API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/connectors/{id}/notion-sync` | Targets, `last_synced_at`, `stale` (>24h) |
| PUT | `/api/connectors/{id}/notion-sync` | Set `targets`, optional `departmentId` |
| GET | `/api/connectors/{id}/notion-sync/search?q=` | Search workspace (`type=page` or `database`) |
| POST | `/api/connectors/{id}/notion-sync/run` | Queue ingest jobs |

### Example: configure targets

```json
PUT /api/connectors/{connector_id}/notion-sync
{
  "targets": [
    { "id": "page-uuid", "type": "page", "title": "Engineering playbook" },
    { "id": "db-uuid", "type": "database", "title": "Incident runbooks" }
  ],
  "departmentId": "optional-dept-uuid"
}
```

## RAG pipeline

Each page is ingested via `rag_ingest_jobs` with `external_id` `notion:page:{id}`. Requires the ingest worker and `OPENAI_API_KEY` for embeddings.

## Code

- `backend/app/connectors/notion_oauth.py`
- `backend/app/connectors/notion.py`
- `backend/app/services/notion_sync_service.py`
- `backend/app/routers/notion_sync.py`
