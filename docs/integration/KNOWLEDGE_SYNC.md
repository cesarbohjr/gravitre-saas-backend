# Knowledge sync scheduler (STA-45)

Unified scheduled and webhook-triggered sync from knowledge connectors (Notion v1) into RAG ingest jobs.

## Components

| Piece | Role |
|-------|------|
| `knowledge_sync_jobs` | Per-run audit row (pages, ingest jobs queued, status) |
| In-process scheduler | `KNOWLEDGE_SYNC_INTERVAL_SECONDS` (default 3600) |
| Internal cron | `POST /api/internal/knowledge/sync-due` |
| Webhook hook | `POST /api/webhooks/knowledge/{connector_id}/sync` |

## Notion (v1)

Uses [NOTION.md](./NOTION.md) targets and `connector.sync_frequency` (e.g. `1h`, `24h`, `daily`).

- **Schedule:** scheduler picks connectors past `notion_last_synced_at` + interval
- **Manual:** `POST /api/connectors/{id}/sync` or `POST /api/admin/knowledge/connectors/{id}/sync`
- **Webhook:** optional `X-Webhook-Secret` matching `connectors.config.webhook_secret`

## Operator cron (GitHub Actions)

Workflow: `.github/workflows/knowledge-sync.yml` (hourly at :15, offset from usage sync).

Requires repo secret `INTERNAL_API_SECRET` matching Railway `INTERNAL_API_SECRET`.

```http
POST https://<api>/api/internal/knowledge/sync-due
X-Internal-Secret: <INTERNAL_API_SECRET>
```

Manual: GitHub Actions → **Knowledge Sync** → Run workflow.

## Admin

```http
GET /api/admin/knowledge/sync-jobs?connectorId=<uuid>
POST /api/admin/knowledge/connectors/{connector_id}/sync
```

## Audit events

- `knowledge.sync.started`
- `knowledge.sync.completed` — `pages_synced`, `ingest_jobs_queued`
- `knowledge.sync.failed`

Chunk counts are recorded when the RAG ingest worker completes (`rag.ingest.completed`).

## Env

```env
KNOWLEDGE_SYNC_INTERVAL_SECONDS=3600
INTERNAL_API_SECRET=...
```

Set `KNOWLEDGE_SYNC_INTERVAL_SECONDS=0` to disable the in-process loop (use cron only).

## Code

- `supabase/migrations/20260603100000_knowledge_sync_jobs.sql`
- `backend/app/services/knowledge_sync_service.py`
- `backend/app/knowledge/sync_scheduler.py`
- `backend/app/routers/knowledge_sync.py`

## Next (STA-46)

HubSpot notes and Zendesk resolved tickets → same job framework.
