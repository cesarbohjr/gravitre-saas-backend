# Checkpoint plan: applying `20261012070000_agent_memory_source_lineage.sql`

Status: **not applied anywhere in production. Applying it needs the owner's separate, explicit authorization.** This plan is for that later step. Nothing in PR #374 applies it, turns a flag on, or runs a live purge.

Project: Supabase `smyeexlrqdpymwjmgzqu`. All checks run in the SQL editor or with psql as an operator. Each checkpoint has a stop condition: if it fails, stop, record it, and do not continue.

## What the migration does

- Adds nullable `agent_memories.source_connector_id` / `source_record_ref`, and `entity_observations.source_connector_id` when that table exists. Adds two partial indexes, which start empty.
- Drops the never-applied four-argument draft of `purge_connector_memories` (`IF EXISTS`), then creates `purge_connector_memories(uuid, uuid, timestamptz, boolean, text)`. It is `SECURITY DEFINER` and executable by `service_role` only.
- It does not write any rows, change any flag, or run a purge. All statements are idempotent and the file can be re-run.

## Checkpoint 0: authorization and state

- [ ] Owner's written go for this migration (separate from the PR's merge).
- [ ] PR #374 is merged, or the exact file at the PR head SHA is the one being applied. Record its `sha256sum`.
- [ ] Backend flags: `MEMORY_SOURCE_LINEAGE_ENABLED` unset/false, `SOURCE_PURGE_DRY_RUN` unset/true. With these, deploying the backend before or after the migration is safe: the disconnect handler logs and skips a missing function, and writers send no lineage columns.
- [ ] Applied ledger: `20261012024200_source_lifecycle_purge` applied, `20261012070000` not applied:

```sql
SELECT version FROM supabase_migrations.schema_migrations
 WHERE version IN ('20261012024200', '20261012040000', '20261012070000') ORDER BY 1;
```

## Checkpoint 1: pre-checks (read-only)

```sql
-- Dependencies
SELECT to_regclass('public.source_purge_receipts');                 -- expect not NULL
SELECT count(*) FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'agent_memories'
   AND column_name IN ('is_current', 'superseded_by', 'valid_until', 'memory_key',
                       'source_class', 'expires_at', 'is_active');  -- expect 7
SELECT to_regclass('public.entity_observations'), to_regclass('public.entity_behavior_signals');
                                                                      -- note: NULL means the observation part is skipped
-- Not yet applied
SELECT count(*) FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name IN ('agent_memories', 'entity_observations')
   AND column_name IN ('source_connector_id', 'source_record_ref');  -- expect 0
SELECT oid::regprocedure FROM pg_proc
 WHERE pronamespace = 'public'::regnamespace AND proname = 'purge_connector_memories'; -- expect 0 rows
-- Size of the index builds (each scans its table once under a SHARE lock)
SELECT count(*) FROM public.agent_memories;
SELECT count(*) FROM public.entity_observations;                    -- skip if the table is absent
-- Lock check: no long transaction holding these tables
SELECT pid, state, xact_start, left(query, 80) FROM pg_stat_activity
 WHERE state <> 'idle' AND xact_start < now() - interval '1 minute';
```

Stop if any expectation fails, or if a table holds more than about 5M rows. In that case, plan a `CREATE INDEX CONCURRENTLY` variant first. Supabase runs a migration file in a single transaction, so it cannot build an index concurrently.

Also run the legacy audit (`memory-lineage-legacy-audit-2026-10-12.sql`, queries 1–3 and 5) and save the output. It is the "before" picture.

## Checkpoint 2: apply

- Apply the single file through the normal Supabase migration path. Record the start and end time.
- Expected duration: about as long as two index builds over the row counts above. While the indexes build, writes to `agent_memories` and `entity_observations` wait.

## Checkpoint 3: post-checks (read-only)

```sql
SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name IN ('agent_memories', 'entity_observations')
   AND column_name IN ('source_connector_id', 'source_record_ref') ORDER BY 1, 2;
-- expect 3 rows, all nullable (2 if entity_observations is absent)
SELECT indexname, indexdef FROM pg_indexes
 WHERE indexname IN ('idx_agent_memories_org_source_connector',
                     'idx_entity_observations_org_source_connector');
SELECT oid::regprocedure, prosecdef FROM pg_proc
 WHERE pronamespace = 'public'::regnamespace AND proname = 'purge_connector_memories';
-- expect exactly one: purge_connector_memories(uuid,uuid,timestamp with time zone,boolean,text), t
SELECT has_function_privilege('anon', 'public.purge_connector_memories(uuid,uuid,timestamptz,boolean,text)', 'EXECUTE'),
       has_function_privilege('authenticated', 'public.purge_connector_memories(uuid,uuid,timestamptz,boolean,text)', 'EXECUTE'),
       has_function_privilege('service_role', 'public.purge_connector_memories(uuid,uuid,timestamptz,boolean,text)', 'EXECUTE');
-- expect f, f, t
SELECT count(*) FROM public.agent_memories WHERE source_connector_id IS NOT NULL;   -- expect 0
```

The startup schema check and `/health` should stay green. The backend does not depend on the new columns.

## Checkpoint 4: dry-run verification (no deletion)

These calls run the purge as a plan: `p_dry_run => true` counts and writes nothing except a receipt merge. Run them inside a transaction and roll back so that no receipt row changes either:

```sql
BEGIN;
-- Pick a connector already disconnected (deleted_at set) in a test or internal org first.
SELECT c.id, c.org_id, c.vendor, c.type, c.deleted_at FROM public.connectors c
 WHERE c.deleted_at IS NOT NULL ORDER BY c.deleted_at DESC LIMIT 5;
SELECT public.purge_connector_memories('<org>', '<connector>', '<deleted_at>', true, NULL);
-- expect: agent_memories 0 (nothing is tagged yet), agent_memories_restored 0,
--         entity_observations = untagged rows of that vendor only if no other live connection,
--         entity_observations_unattributed = the rest, receipt_merged true/false.
-- Cross-check by hand:
SELECT count(*) FROM public.entity_observations
 WHERE org_id = '<org>' AND lower(source_system) = '<vendor>' AND created_at <= '<deleted_at>';
-- Tenant isolation: the same connector id with another org must count 0
SELECT public.purge_connector_memories('<another org>', '<connector>', '<deleted_at>', true, NULL);
ROLLBACK;
```

Stop if a dry run counts rows in another org, or if it counts observations of a vendor that still has a live connection.

## Checkpoint 5: before turning anything on (separate decisions)

1. Owner decides the legacy groups (`memory-lineage-legacy-handling-proposal-2026-10-12.md`).
2. `MEMORY_SOURCE_LINEAGE_ENABLED=true` is a separate, explicit owner decision, and only after the migration is applied. It turns on, together: lineage tags on new writes; the read-time filter (memories and observations naming a connector that is deleted, revoked, disconnected or gone are not recalled, failing closed if the liveness read fails); cache invalidation on disconnect; and the memory/observation part of the disconnect purge (dry run still honoured). Before the migration, the filter's lineage read fails and recall returns no memories, so never turn it on first. After it, re-run the post-check count of tagged rows. It should rise only for new connector writes. Watch `memory_source_liveness_failed_closed` (should be zero) and `memory_source_revoked_excluded` in the logs for a day.
3. `SOURCE_PURGE_DRY_RUN=false` (live purge) is another separate decision. It is out of scope for this PR. Until then, every disconnect only records a dry-run receipt, which now includes the memory and observation counts as evidence.

## Rollback

This is safe at any time. It discards lineage tags only and removes no customer data. Turn `MEMORY_SOURCE_LINEAGE_ENABLED` off first.

```sql
DROP FUNCTION IF EXISTS public.purge_connector_memories(uuid, uuid, timestamptz, boolean, text);
DROP INDEX IF EXISTS public.idx_entity_observations_org_source_connector;
ALTER TABLE IF EXISTS public.entity_observations DROP COLUMN IF EXISTS source_connector_id;
DROP INDEX IF EXISTS public.idx_agent_memories_org_source_connector;
ALTER TABLE public.agent_memories DROP COLUMN IF EXISTS source_record_ref,
  DROP COLUMN IF EXISTS source_connector_id;
DELETE FROM supabase_migrations.schema_migrations WHERE version = '20261012070000';
```

After a rollback, the disconnect handler logs `source_purge_memories_unavailable` and continues with the derived-data purge only. Writers retry without the lineage columns.

## Evidence already in the PR (CI, real PostgreSQL)

- `tests/db/test_source_scoped_observation_purge_pg.py`: source-scoped removal, multi-vendor accounts, shared vendor, reconnect, cross-org isolation, dry-run no-op, idempotent rerun, recipients and channels kept.
- `tests/db/test_memory_source_lineage_pg.py`: agent-memory purge scope, reveal rules (provenance, retention, expiry), receipt merge, grants, idempotent re-apply.
- `tests/db/test_memory_lineage_legacy_audit_pg.py`: the audit is read-only and classifies every row.
