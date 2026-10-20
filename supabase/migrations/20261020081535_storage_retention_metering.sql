-- Storage: audit-log retention, per-org storage meter, bring-your-own file storage.
--
-- Applied to production on the owner's go (2026-10-20), after the preflight below,
-- in parts: the full file timed out in the migration tool, so prod stamped one
-- version per part (this file and the storage_* files that follow it, up to
-- 20261020082154_storage_byo_targets.sql), plus 20261020090000_storage_retention_delete_batch.sql.
--
-- Additive only: new tables and functions, no change to existing tables, no data
-- moved or deleted by applying it. Every statement can be re-run. The backend uses
-- it through these settings (on by default since 2026-10-20):
--   AUDIT_RETENTION_DAYS / TELEMETRY_RETENTION_DAYS (365; 0 = keep forever),
--   AUDIT_RETENTION_DRY_RUN (default false), AUDIT_RETENTION_ARCHIVE_ENABLED,
--   STORAGE_METER_ENABLED, STORAGE_QUOTA_ENFORCEMENT_ENABLED, BYO_STORAGE_ENABLED.
--
-- What it adds:
--   1) org_legal_holds: an org with an unreleased hold is skipped by retention
--      entirely (no row of that org is counted or deleted). Set by an operator in SQL.
--   2) data_retention_runs: one receipt per retention run (dry run or real). A partial
--      unique index allows a single 'running' run at a time (multi-replica safe).
--   3) data_retention_candidates / data_retention_fetch_batch / data_retention_delete_batch:
--      service_role only. Whitelisted tables with a floor each, enforced here as well
--      as in the backend (a cutoff newer than the floor raises):
--        audit_logs, audit_events          365 days
--        model_calls                       400 days (agent ROI reads up to 366 days)
--        ai_pipeline_latency               30 days
--        cognitive_turn_traces             30 days
--      guardrail_events is deliberately not in the list (security evidence).
--      Rows of audit_logs / audit_events whose action mentions an approval or a
--      rejection (approval trail) are never selected. Deletes are bounded batches,
--      oldest first, FOR UPDATE SKIP LOCKED, so locks stay short.
--   4) org_storage_usage_snapshots: one row per org per day; org members read their own
--      org, the service role writes.
--   5) compute_org_storage_usage(p_org_id): service_role only. Approximate bytes per org
--      and category. Method: for each table, pg_total_relation_size (heap + TOAST +
--      indexes, so embeddings and their vector indexes are included) is split between
--      orgs in proportion to their row counts (one grouped count per table, served by
--      the org_id indexes). Files: exact object sizes from storage.objects whose first
--      path segment is the org id. Tables without org_id (platform knowledge_chunks)
--      are not attributed to any org.
--   6) org_storage_targets: one S3-compatible target per org. Access key id and secret
--      are stored only encrypted (backend CONNECTOR_SECRETS_ENCRYPTION_KEY, same as
--      connector secrets). No client access at all: the API returns a redacted view.
--   7) org_file_objects: where each uploaded file was stored ('supabase' or 'byo'), so
--      reads resolve from the right place. Org members read their own org's rows.
--      Database rows (memories, chunks, embeddings) always stay in Supabase.
--   8) Private storage bucket 'audit-archive' (when the storage schema exists).
--
-- Supabase applies each migration file in one transaction (no explicit BEGIN/COMMIT).
-- Lock impact: none on existing tables (new objects only).
--
-- Preflight (read-only; run before applying):
--   SELECT to_regclass('public.organizations'), to_regclass('public.organization_members');
--                                                                   -- expect both not NULL
--   SELECT to_regclass('public.org_legal_holds'), to_regclass('public.data_retention_runs'),
--          to_regclass('public.org_storage_usage_snapshots'), to_regclass('public.org_storage_targets'),
--          to_regclass('public.org_file_objects');                 -- expect all NULL
--   SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace
--     AND proname IN ('compute_org_storage_usage', 'data_retention_candidates',
--                     'data_retention_fetch_batch', 'data_retention_delete_batch'); -- expect 0 rows
--   SELECT id, public FROM storage.buckets WHERE id = 'audit-archive';  -- expect 0 rows
--
-- Post-checks (read-only; after applying):
--   SELECT count(*) FROM public.org_legal_holds;                     -- expect 0
--   SELECT has_function_privilege('authenticated',
--     'public.compute_org_storage_usage(uuid)', 'EXECUTE');           -- expect false
--   SELECT has_function_privilege('service_role',
--     'public.compute_org_storage_usage(uuid)', 'EXECUTE');           -- expect true
--   SELECT category, sum(bytes) FROM public.compute_org_storage_usage(NULL) GROUP BY 1;
--                                                                   -- run as service role / SQL editor
--   SELECT * FROM public.data_retention_candidates('audit_logs', now() - interval '365 days');
--                                                                   -- read-only count per org
--   SELECT public FROM storage.buckets WHERE id = 'audit-archive';   -- expect false
--
-- Rollback (manual; set the flags above back to their defaults first):
--   DROP FUNCTION IF EXISTS public.compute_org_storage_usage(uuid);
--   DROP FUNCTION IF EXISTS public.data_retention_delete_batch(text, uuid, timestamptz, int, uuid[]);
--   DROP FUNCTION IF EXISTS public.data_retention_fetch_batch(text, uuid, timestamptz, int);
--   DROP FUNCTION IF EXISTS public.data_retention_candidates(text, timestamptz);
--   DROP FUNCTION IF EXISTS public.data_retention_where(text);
--   DROP FUNCTION IF EXISTS public.data_retention_floor_days(text);
--   DROP TABLE IF EXISTS public.org_file_objects;
--   DROP TABLE IF EXISTS public.org_storage_targets;
--   DROP TABLE IF EXISTS public.org_storage_usage_snapshots;
--   DROP TABLE IF EXISTS public.data_retention_runs;
--   DROP TABLE IF EXISTS public.org_legal_holds;
--   (Leave the 'audit-archive' bucket: it may hold archives that were written.)
--   Files already written to a customer's own bucket stay there; dropping
--   org_file_objects loses the record of where they are.


-- -----------------------------------------------------------------------------
-- 1) Legal holds
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.org_legal_holds (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  reason text NOT NULL,
  placed_by uuid,
  placed_at timestamptz NOT NULL DEFAULT now(),
  released_at timestamptz,
  released_by uuid
);
