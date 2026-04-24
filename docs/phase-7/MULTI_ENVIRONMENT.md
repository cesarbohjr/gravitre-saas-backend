# Phase 7: Multi-Environment Support (Per Org)

## Current Architectural Limitation
- All workflow runs, connectors, and RAG assets are scoped only by org.
- There is no built-in isolation for dev/staging/prod within an org.

## Target Architecture
- Add an `environments` table (org-scoped) and store `environment` on core tables.
- Default environment is `default` to keep backward compatibility.
- Environment selection is request-driven via `X-Environment` header.

## Minimal Implementation Plan
- Create `public.environments` and backfill `default` for existing orgs.
- Add `environment` columns with default `default` to:
  - `workflow_runs`, `connectors`, `rag_sources`, `rag_documents`, `rag_chunks`,
    `rag_embeddings`, `rag_ingest_jobs`, `rag_retrieval_logs`
- Update RAG search RPC to filter by environment.
- Update ingestion job claim RPC to return environment.
- Add environment context dependency and plumb to routers/services.

## Required Migrations
- `supabase/migrations/20250220000006_phase7_multi_environment.sql`

## Integration Changes
- New `get_environment_context` dependency reads `X-Environment` (defaults to `default`).
- Workflow execute/dry-run include `environment` on runs and policy evaluation.
- Connector CRUD and handler lookups are filtered by environment.
- RAG source/document ingestion/retrieval is filtered by environment.

## Risks
- Header misuse can leak data across environments if callers do not set it consistently.
- Environment column defaults must remain non-breaking for legacy clients.

## Future Scaling Notes
- Add environment lifecycle APIs (create/list/delete) if needed.
- Add environment-level quotas or limits via policy engine.
