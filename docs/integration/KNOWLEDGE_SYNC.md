# Knowledge sync scheduler (STA-45)

Unified scheduled and webhook-triggered sync from knowledge connectors (Notion v1) into RAG ingest jobs.

## Components

| Piece | Role |
|-------|------|
| `knowledge_sync_jobs` | Per-run audit row (pages, ingest jobs queued, status) |
| In-process scheduler | `KNOWLEDGE_SYNC_INTERVAL_SECONDS` (default 3600) |
| Internal cron | `POST /api/internal/knowledge/sync-due` |
| Webhook hook | `POST /api/webhooks/knowledge/{connector_id}/sync` |

## Sources (STA-45 / STA-46)

| Connector | Content | Config |
|-----------|---------|--------|
| Notion | Pages/databases from targets | `notion_sync_targets` — see [NOTION.md](./NOTION.md) |
| HubSpot | Notes + emails (incremental) | Enabled by default; `hubspot_knowledge_sync_enabled: false` to disable |
| Zendesk | Resolved tickets | Enabled by default; `zendesk_knowledge_sync_enabled: false` to disable |

All use `connector.sync_frequency` (e.g. `1h`, `24h`, `daily`) and store `*_last_synced_at` in `connectors.config`.

## Notion

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

## HubSpot + Zendesk (STA-46)

- HubSpot: CRM search on `notes` and `emails` since `hubspot_last_synced_at` (first run: last 24h).
- Zendesk: search `type:ticket status:solved updated>=<date>` since `zendesk_last_synced_at`.
- RAG sources: `hubspot_rag_source_id`, `zendesk_rag_source_id` on connector config.

## Next

Confluence sync → RAG (STA-44).
