# Voyage Re-index Runbook

## What This Does

Re-embeds all documents in the Gravitre knowledge base using Voyage `voyage-3` (1024-dim) instead of OpenAI `text-embedding-3-small` (1536-dim). After this runbook, semantic search can use Voyage embeddings and the Voyage failover will work correctly.

## When To Run This

Only when:

- `VOYAGE_API_KEY` is confirmed valid
- You have verified `voyage-3` embedding quality on a sample of your document corpus
- You have a maintenance window (re-indexing will temporarily degrade semantic search quality for documents being migrated)

## Pre-flight Checks

- [ ] `VOYAGE_API_KEY` is set in Railway
- [ ] Backup of current embeddings taken (SQL export below)
- [ ] Voyage API quota sufficient for corpus size: estimate N documents × avg tokens per doc
- [ ] `VOYAGE_EMBEDDING_ENABLED=false` in Railway (keep false until re-index is complete)

```sql
-- Backup current vectors (run in Supabase SQL editor)
COPY (
  SELECT chunk_id, org_id, embedding::text
  FROM public.rag_embeddings
) TO STDOUT WITH CSV HEADER;
```

## The Dimension Problem

pgvector requires all vectors in a column to be the same dimension. The current corpus uses 1536-dim (OpenAI). Voyage uses 1024-dim. You cannot mix dimensions in the same column without an `ALTER TABLE`.

**Options:**

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A (recommended) | Add `embedding_voyage vector(1024)` alongside existing `embedding` | Zero downtime, gradual migration | Doubles storage during transition |
| B | Maintenance window: alter column to 1024 and re-embed all | Clean schema | Downtime or dual-write required |

## Recommended Approach (Option A)

### Step 1: Add voyage embedding column

Migration `supabase/migrations/20260531120100_rag_embeddings_voyage.sql` adds:

```sql
ALTER TABLE public.rag_embeddings
  ADD COLUMN IF NOT EXISTS embedding_voyage vector(1024);
```

Apply: `supabase db push`

### Step 2: Update `rag_search` RPC

Extend the RPC to accept an `embedding_model` parameter and query `embedding_voyage` when model is `voyage-3`. (Not yet wired in production — do this before enabling Voyage search.)

### Step 3: Run reindex script

```bash
cd backend
python scripts/reindex_with_voyage.py --batch-size 50 --delay-ms 100
```

Dry run first:

```bash
python scripts/reindex_with_voyage.py --dry-run --batch-size 10
```

### Step 4: Verify quality on a sample

Run 5–10 representative queries via `/api/rag/query` and compare results to OpenAI baseline.

### Step 5: Enable Voyage

Set `VOYAGE_EMBEDDING_ENABLED=true` in Railway.

### Step 6: Monitor RAG quality metrics for 24 hours

Watch `embedding_method` in RAG response metrics and error rates.

### Step 7: Reclaim storage (optional)

After confirmed good, optionally drop the original `embedding` column to reclaim storage.

## Rollback

Set `VOYAGE_EMBEDDING_ENABLED=false` in Railway. The system immediately falls back to OpenAI embeddings and keyword search. No data loss. No migration needed.
