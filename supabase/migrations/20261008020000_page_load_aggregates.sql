-- Page-load aggregates computed in SQL instead of pulling every row into Python.
--
-- /api/metrics/overview (and /api/metrics/export) and /api/marketplace/categories
-- (and /api/marketplace/analytics/summary) used to select every matching row and
-- count in Python. That was slow (marketplace categories p75 9.1s) and silently
-- capped counts at PostgREST max_rows (1000).
--
-- Filters intentionally mirror the previous Python code exactly:
--   metrics_overview_counts:
--     workflow_defs  WHERE org_id = p_org_id                 (active = status 'active')
--     workflow_runs  WHERE org_id = p_org_id
--                      AND created_at >= p_start_at AND created_at < p_end_at
--                    (completed/failed by status; duration over non-null duration_ms)
--     connectors     WHERE org_id = p_org_id                 (active = status 'active')
--   marketplace_category_counts:
--     marketplace_assets WHERE status = 'published'
--       AND (visibility = 'public' OR (visibility = 'internal' AND org_id = p_org_id))
--     NULL or '' category/department/asset_type bucket as
--     'uncategorized' / 'general' / 'unknown' (Python's `value or default`).
--
-- Both are read-only, STABLE, SECURITY INVOKER (callers use the service-role key,
-- which already bypasses RLS), pinned search_path, and executable by service_role only.
-- Additive and idempotent (CREATE OR REPLACE); the backend falls back to a paged
-- Python path while this migration is not yet applied.

CREATE OR REPLACE FUNCTION public.metrics_overview_counts(
  p_org_id uuid,
  p_start_at timestamptz,
  p_end_at timestamptz
)
RETURNS jsonb
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  SELECT jsonb_build_object(
    'total_workflows',   wf.total,
    'active_workflows',  wf.active,
    'total_runs',        runs.total,
    'completed_runs',    runs.completed,
    'failed_runs',       runs.failed,
    'duration_count',    runs.duration_count,
    'duration_sum_ms',   runs.duration_sum_ms,
    'total_connectors',  conn.total,
    'active_connectors', conn.active
  )
  FROM
    (
      SELECT count(*) AS total,
             count(*) FILTER (WHERE d.status = 'active') AS active
        FROM public.workflow_defs d
       WHERE d.org_id = p_org_id
    ) AS wf,
    (
      SELECT count(*) AS total,
             count(*) FILTER (WHERE r.status = 'completed') AS completed,
             count(*) FILTER (WHERE r.status = 'failed') AS failed,
             count(r.duration_ms) AS duration_count,
             coalesce(sum(r.duration_ms), 0) AS duration_sum_ms
        FROM public.workflow_runs r
       WHERE r.org_id = p_org_id
         AND r.created_at >= p_start_at
         AND r.created_at < p_end_at
    ) AS runs,
    (
      SELECT count(*) AS total,
             count(*) FILTER (WHERE c.status = 'active') AS active
        FROM public.connectors c
       WHERE c.org_id = p_org_id
    ) AS conn;
$$;

REVOKE ALL ON FUNCTION public.metrics_overview_counts(uuid, timestamptz, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.metrics_overview_counts(uuid, timestamptz, timestamptz) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.metrics_overview_counts(uuid, timestamptz, timestamptz) TO service_role;

COMMENT ON FUNCTION public.metrics_overview_counts(uuid, timestamptz, timestamptz) IS
  'Dashboard overview counts (workflows, runs in [p_start_at, p_end_at), connectors) for one org.';


CREATE OR REPLACE FUNCTION public.marketplace_category_counts(
  p_org_id uuid
)
RETURNS jsonb
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  WITH visible AS (
    SELECT coalesce(nullif(a.category, ''), 'uncategorized') AS category,
           coalesce(nullif(a.department, ''), 'general') AS department,
           coalesce(nullif(a.asset_type, ''), 'unknown') AS asset_type
      FROM public.marketplace_assets a
     WHERE a.status = 'published'
       AND (
         a.visibility = 'public'
         OR (a.visibility = 'internal' AND a.org_id = p_org_id)
       )
  )
  SELECT jsonb_build_object(
    'total_assets', (SELECT count(*) FROM visible),
    'categories', coalesce(
      (SELECT jsonb_object_agg(g.k, g.n)
         FROM (SELECT v.category AS k, count(*) AS n FROM visible v GROUP BY v.category) g),
      '{}'::jsonb
    ),
    'departments', coalesce(
      (SELECT jsonb_object_agg(g.k, g.n)
         FROM (SELECT v.department AS k, count(*) AS n FROM visible v GROUP BY v.department) g),
      '{}'::jsonb
    ),
    'asset_types', coalesce(
      (SELECT jsonb_object_agg(g.k, g.n)
         FROM (SELECT v.asset_type AS k, count(*) AS n FROM visible v GROUP BY v.asset_type) g),
      '{}'::jsonb
    )
  );
$$;

REVOKE ALL ON FUNCTION public.marketplace_category_counts(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.marketplace_category_counts(uuid) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.marketplace_category_counts(uuid) TO service_role;

COMMENT ON FUNCTION public.marketplace_category_counts(uuid) IS
  'Published marketplace catalog counts by category/department/asset_type visible to one org.';
