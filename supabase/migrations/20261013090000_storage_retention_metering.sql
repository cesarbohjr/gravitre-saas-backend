-- Storage: audit-log retention, per-org storage meter, bring-your-own file storage.
--
-- NOT APPLIED TO PRODUCTION. Needs the owner's separate authorization and the
-- checkpoints below (also in the PR description).
--
-- Additive only: new tables and functions, no change to existing tables, no data
-- moved or deleted by applying it. Every statement can be re-run. The backend uses
-- none of it until the matching flags are on (all default off):
--   AUDIT_RETENTION_DAYS / TELEMETRY_RETENTION_DAYS (0 = keep forever),
--   AUDIT_RETENTION_DRY_RUN (default true), AUDIT_RETENTION_ARCHIVE_ENABLED,
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

CREATE INDEX IF NOT EXISTS idx_org_legal_holds_active
  ON public.org_legal_holds (org_id)
  WHERE released_at IS NULL;

COMMENT ON TABLE public.org_legal_holds IS
  'While a hold has released_at NULL, data retention skips the org entirely (nothing counted or deleted).';

ALTER TABLE public.org_legal_holds ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.org_legal_holds FROM anon, authenticated;
GRANT ALL ON public.org_legal_holds TO service_role;

-- -----------------------------------------------------------------------------
-- 2) Retention receipts
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.data_retention_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  dry_run boolean NOT NULL,
  status text NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'completed', 'partial', 'failed', 'abandoned')),
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  totals jsonb NOT NULL DEFAULT '{}'::jsonb,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  error text
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_data_retention_runs_one_running
  ON public.data_retention_runs ((true))
  WHERE status = 'running';

CREATE INDEX IF NOT EXISTS idx_data_retention_runs_started
  ON public.data_retention_runs (started_at DESC);

ALTER TABLE public.data_retention_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.data_retention_runs FROM anon, authenticated;
GRANT ALL ON public.data_retention_runs TO service_role;

-- -----------------------------------------------------------------------------
-- 3) Retention functions
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.data_retention_floor_days(p_table text)
RETURNS int
LANGUAGE sql
IMMUTABLE
SET search_path = public, pg_temp
AS $$
  SELECT CASE p_table
    WHEN 'audit_logs' THEN 365
    WHEN 'audit_events' THEN 365
    WHEN 'model_calls' THEN 400
    WHEN 'ai_pipeline_latency' THEN 30
    WHEN 'cognitive_turn_traces' THEN 30
    ELSE NULL
  END;
$$;

-- Extra predicate on alias t: approval / rejection rows of the audit trail are kept.
CREATE OR REPLACE FUNCTION public.data_retention_where(p_table text)
RETURNS text
LANGUAGE sql
IMMUTABLE
SET search_path = public, pg_temp
AS $$
  SELECT CASE
    WHEN p_table IN ('audit_logs', 'audit_events')
      THEN ' AND t.action !~* ''(approv|reject)'''
    ELSE ''
  END;
$$;

CREATE OR REPLACE FUNCTION public.data_retention_candidates(
  p_table text,
  p_cutoff timestamptz
) RETURNS TABLE (org_id uuid, row_count bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_floor int := public.data_retention_floor_days(p_table);
BEGIN
  IF v_floor IS NULL THEN
    RAISE EXCEPTION 'data_retention: table % is not eligible', p_table;
  END IF;
  IF p_cutoff IS NULL OR p_cutoff > now() - make_interval(days => v_floor) THEN
    RAISE EXCEPTION 'data_retention: cutoff for % is inside the % day floor', p_table, v_floor;
  END IF;
  IF to_regclass(format('public.%I', p_table)) IS NULL THEN
    RETURN;
  END IF;
  RETURN QUERY EXECUTE format(
    'SELECT t.org_id, count(*)::bigint
       FROM public.%I t
      WHERE t.created_at < $1 %s
        AND NOT EXISTS (
          SELECT 1 FROM public.org_legal_holds h
           WHERE h.org_id = t.org_id AND h.released_at IS NULL)
      GROUP BY t.org_id
      ORDER BY t.org_id',
    p_table, public.data_retention_where(p_table)
  ) USING p_cutoff;
END;
$$;

CREATE OR REPLACE FUNCTION public.data_retention_fetch_batch(
  p_table text,
  p_org_id uuid,
  p_cutoff timestamptz,
  p_batch int DEFAULT 1000
) RETURNS SETOF jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_floor int := public.data_retention_floor_days(p_table);
  v_batch int := least(greatest(coalesce(p_batch, 1000), 1), 10000);
BEGIN
  IF v_floor IS NULL THEN
    RAISE EXCEPTION 'data_retention: table % is not eligible', p_table;
  END IF;
  IF p_cutoff IS NULL OR p_cutoff > now() - make_interval(days => v_floor) THEN
    RAISE EXCEPTION 'data_retention: cutoff for % is inside the % day floor', p_table, v_floor;
  END IF;
  IF p_org_id IS NULL OR to_regclass(format('public.%I', p_table)) IS NULL THEN
    RETURN;
  END IF;
  IF EXISTS (SELECT 1 FROM public.org_legal_holds h
              WHERE h.org_id = p_org_id AND h.released_at IS NULL) THEN
    RETURN;
  END IF;
  RETURN QUERY EXECUTE format(
    'SELECT to_jsonb(t)
       FROM public.%I t
      WHERE t.org_id = $1 AND t.created_at < $2 %s
      ORDER BY t.created_at, t.id
      LIMIT $3',
    p_table, public.data_retention_where(p_table)
  ) USING p_org_id, p_cutoff, v_batch;
END;
$$;

-- Deletes at most p_batch rows of one org, oldest first. With p_ids (archive mode) only
-- those ids are deleted, and only while they still match every predicate.
CREATE OR REPLACE FUNCTION public.data_retention_delete_batch(
  p_table text,
  p_org_id uuid,
  p_cutoff timestamptz,
  p_batch int DEFAULT 1000,
  p_ids uuid[] DEFAULT NULL
) RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_floor int := public.data_retention_floor_days(p_table);
  v_batch int := least(greatest(coalesce(p_batch, 1000), 1), 10000);
  v_deleted int := 0;
BEGIN
  IF v_floor IS NULL THEN
    RAISE EXCEPTION 'data_retention: table % is not eligible', p_table;
  END IF;
  IF p_cutoff IS NULL OR p_cutoff > now() - make_interval(days => v_floor) THEN
    RAISE EXCEPTION 'data_retention: cutoff for % is inside the % day floor', p_table, v_floor;
  END IF;
  IF p_org_id IS NULL OR to_regclass(format('public.%I', p_table)) IS NULL THEN
    RETURN 0;
  END IF;
  IF EXISTS (SELECT 1 FROM public.org_legal_holds h
              WHERE h.org_id = p_org_id AND h.released_at IS NULL) THEN
    RETURN 0;
  END IF;
  IF p_ids IS NOT NULL THEN
    IF cardinality(p_ids) > 10000 THEN
      RAISE EXCEPTION 'data_retention: at most 10000 ids per batch';
    END IF;
    EXECUTE format(
      'DELETE FROM public.%I t
        WHERE t.id = ANY($3) AND t.org_id = $1 AND t.created_at < $2 %s',
      p_table, public.data_retention_where(p_table)
    ) USING p_org_id, p_cutoff, p_ids;
  ELSE
    EXECUTE format(
      'WITH doomed AS (
         SELECT t.id FROM public.%I t
          WHERE t.org_id = $1 AND t.created_at < $2 %s
          ORDER BY t.created_at, t.id
          LIMIT $3
          FOR UPDATE SKIP LOCKED)
       DELETE FROM public.%I d USING doomed WHERE d.id = doomed.id',
      p_table, public.data_retention_where(p_table), p_table
    ) USING p_org_id, p_cutoff, v_batch;
  END IF;
  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  RETURN v_deleted;
END;
$$;

REVOKE ALL ON FUNCTION public.data_retention_floor_days(text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.data_retention_where(text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.data_retention_candidates(text, timestamptz) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.data_retention_fetch_batch(text, uuid, timestamptz, int)
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.data_retention_delete_batch(text, uuid, timestamptz, int, uuid[])
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.data_retention_floor_days(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.data_retention_where(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.data_retention_candidates(text, timestamptz) TO service_role;
GRANT EXECUTE ON FUNCTION public.data_retention_fetch_batch(text, uuid, timestamptz, int) TO service_role;
GRANT EXECUTE ON FUNCTION public.data_retention_delete_batch(text, uuid, timestamptz, int, uuid[])
  TO service_role;

-- -----------------------------------------------------------------------------
-- 4) Storage usage snapshots
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.org_storage_usage_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  snapshot_date date NOT NULL DEFAULT (now() AT TIME ZONE 'utc')::date,
  captured_at timestamptz NOT NULL DEFAULT now(),
  total_bytes bigint NOT NULL DEFAULT 0 CHECK (total_bytes >= 0),
  categories jsonb NOT NULL DEFAULT '{}'::jsonb,
  method text NOT NULL DEFAULT 'proportional-relation-size-v1',
  CONSTRAINT org_storage_usage_snapshots_once_per_day UNIQUE (org_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_org_storage_usage_snapshots_org_captured
  ON public.org_storage_usage_snapshots (org_id, captured_at DESC);

ALTER TABLE public.org_storage_usage_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_storage_usage_snapshots_read ON public.org_storage_usage_snapshots;
CREATE POLICY org_storage_usage_snapshots_read ON public.org_storage_usage_snapshots FOR SELECT
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

REVOKE INSERT, UPDATE, DELETE ON public.org_storage_usage_snapshots FROM anon, authenticated;
GRANT SELECT ON public.org_storage_usage_snapshots TO authenticated;
GRANT ALL ON public.org_storage_usage_snapshots TO service_role;

-- -----------------------------------------------------------------------------
-- 5) Storage meter
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.compute_org_storage_usage(p_org_id uuid DEFAULT NULL)
RETURNS TABLE (org_id uuid, category text, source text, bytes bigint, row_count bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  r record;
  v_size bigint;
BEGIN
  FOR r IN
    SELECT v.category, v.tbl
      FROM (VALUES
        ('knowledge', 'rag_sources'),
        ('knowledge', 'rag_documents'),
        ('knowledge', 'rag_chunks'),
        ('knowledge', 'rag_embeddings'),
        ('memories', 'agent_memories'),
        ('memories', 'agent_memory_history'),
        ('memories', 'org_memory_entity_embeddings'),
        ('conversations', 'conversations'),
        ('conversations', 'conversation_messages'),
        ('audit', 'audit_logs'),
        ('audit', 'audit_events')
      ) AS v(category, tbl)
  LOOP
    IF to_regclass(format('public.%I', r.tbl)) IS NULL THEN
      CONTINUE;
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns c
       WHERE c.table_schema = 'public' AND c.table_name = r.tbl AND c.column_name = 'org_id'
    ) THEN
      CONTINUE;
    END IF;
    v_size := pg_total_relation_size(format('public.%I', r.tbl)::regclass);
    RETURN QUERY EXECUTE format(
      'WITH c AS (SELECT t.org_id AS o, count(*)::bigint AS n FROM public.%I t GROUP BY t.org_id),
            s AS (SELECT coalesce(sum(c.n), 0)::numeric AS total FROM c)
       SELECT c.o, %L::text, %L::text,
              CASE WHEN s.total > 0 THEN round($1::numeric * c.n / s.total)::bigint ELSE 0::bigint END,
              c.n
         FROM c CROSS JOIN s
        WHERE c.o IS NOT NULL AND ($2::uuid IS NULL OR c.o = $2)',
      r.tbl, r.category, r.tbl
    ) USING v_size, p_org_id;
  END LOOP;

  IF to_regclass('storage.objects') IS NOT NULL THEN
    RETURN QUERY EXECUTE
      $q$
      SELECT o.id,
             CASE WHEN so.bucket_id = 'audit-archive' THEN 'audit' ELSE 'files' END,
             'storage.objects:' || so.bucket_id,
             coalesce(sum(CASE WHEN (so.metadata->>'size') ~ '^[0-9]+$'
                               THEN (so.metadata->>'size')::bigint ELSE 0 END), 0)::bigint,
             count(*)::bigint
        FROM storage.objects so
        JOIN public.organizations o ON o.id::text = split_part(so.name, '/', 1)
       WHERE ($1::uuid IS NULL OR o.id = $1)
       GROUP BY o.id, so.bucket_id
      $q$
    USING p_org_id;
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.compute_org_storage_usage(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.compute_org_storage_usage(uuid) TO service_role;

COMMENT ON FUNCTION public.compute_org_storage_usage(uuid) IS
  'Approximate bytes per org and category: table size (incl. TOAST and indexes) split by org row share; files exact from storage.objects.';

-- -----------------------------------------------------------------------------
-- 6) Bring-your-own storage target
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.org_storage_targets (
  org_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
  provider text NOT NULL DEFAULT 's3' CHECK (provider IN ('s3')),
  endpoint_url text,
  region text NOT NULL,
  bucket text NOT NULL,
  path_prefix text NOT NULL DEFAULT '',
  access_key_id_enc text NOT NULL,
  secret_access_key_enc text NOT NULL,
  access_key_hint text,
  status text NOT NULL DEFAULT 'untested' CHECK (status IN ('untested', 'verified', 'failed')),
  last_tested_at timestamptz,
  last_test_error text,
  created_by uuid,
  updated_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.org_storage_targets IS
  'Org-owned S3-compatible bucket for uploaded files only. Credentials encrypted by the backend; never readable by clients.';

ALTER TABLE public.org_storage_targets ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.org_storage_targets FROM anon, authenticated;
GRANT ALL ON public.org_storage_targets TO service_role;

-- -----------------------------------------------------------------------------
-- 7) Where each uploaded file lives
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.org_file_objects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  location text NOT NULL CHECK (location IN ('supabase', 'byo')),
  bucket text NOT NULL,
  object_key text NOT NULL,
  logical_bucket text NOT NULL,
  logical_path text NOT NULL,
  byte_size bigint NOT NULL DEFAULT 0 CHECK (byte_size >= 0),
  content_type text,
  purpose text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT org_file_objects_logical_once UNIQUE (org_id, logical_bucket, logical_path)
);

CREATE INDEX IF NOT EXISTS idx_org_file_objects_org_created
  ON public.org_file_objects (org_id, created_at DESC);

ALTER TABLE public.org_file_objects ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_file_objects_read ON public.org_file_objects;
CREATE POLICY org_file_objects_read ON public.org_file_objects FOR SELECT
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

REVOKE INSERT, UPDATE, DELETE ON public.org_file_objects FROM anon, authenticated;
GRANT SELECT ON public.org_file_objects TO authenticated;
GRANT ALL ON public.org_file_objects TO service_role;

-- -----------------------------------------------------------------------------
-- 8) Private archive bucket
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('storage.buckets') IS NOT NULL THEN
    INSERT INTO storage.buckets (id, name, public)
    VALUES ('audit-archive', 'audit-archive', false)
    ON CONFLICT (id) DO NOTHING;
  END IF;
END
$$;
