-- ============================================
-- GRAVITRE BACKFILL VERIFICATION
-- Run this AFTER migration to validate parity
-- Read-only: no modifications
-- ============================================

-- NOTE:
-- This script is read-only and supports both:
-- - fresh databases (legacy tables may not exist), and
-- - migrated databases (legacy tables still present).
-- Legacy comparison queries use to_regclass('public.<table>') so missing
-- legacy tables return legacy_count = 0 and status = 'NO_LEGACY_TABLE'.

-- 1. ROW COUNTS
SELECT 'workflows' AS table_name, COUNT(*) AS row_count FROM public.workflows
UNION ALL
SELECT 'runs', COUNT(*) FROM public.runs
UNION ALL
SELECT 'run_steps', COUNT(*) FROM public.run_steps
UNION ALL
SELECT 'connected_systems', COUNT(*) FROM public.connected_systems
UNION ALL
SELECT 'agents', COUNT(*) FROM public.agents
UNION ALL
SELECT 'approvals', COUNT(*) FROM public.approvals
UNION ALL
SELECT 'organizations', COUNT(*) FROM public.organizations
UNION ALL
SELECT 'users', COUNT(*) FROM public.users;

-- 2. LEGACY VS CONTRACT COUNTS
WITH workflow_defs_check AS (
  SELECT
    to_regclass('public.workflow_defs') AS legacy_rel,
    (SELECT COUNT(*) FROM public.workflows) AS contract_count
)
SELECT
  'workflow_defs -> workflows' AS migration,
  CASE
    WHEN legacy_rel IS NULL THEN 0::bigint
    ELSE (
      xpath(
        '/row/cnt/text()',
        query_to_xml('SELECT COUNT(*) AS cnt FROM public.workflow_defs', false, true, '')
      )
    )[1]::text::bigint
  END AS legacy_count,
  contract_count,
  CASE
    WHEN legacy_rel IS NULL THEN 'NO_LEGACY_TABLE'
    WHEN contract_count >= (
      xpath(
        '/row/cnt/text()',
        query_to_xml('SELECT COUNT(*) AS cnt FROM public.workflow_defs', false, true, '')
      )
    )[1]::text::bigint THEN 'OK'
    ELSE 'MISMATCH'
  END AS status
FROM workflow_defs_check;

WITH workflow_runs_check AS (
  SELECT
    to_regclass('public.workflow_runs') AS legacy_rel,
    (SELECT COUNT(*) FROM public.runs) AS contract_count
)
SELECT
  'workflow_runs -> runs' AS migration,
  CASE
    WHEN legacy_rel IS NULL THEN 0::bigint
    ELSE (
      xpath(
        '/row/cnt/text()',
        query_to_xml('SELECT COUNT(*) AS cnt FROM public.workflow_runs', false, true, '')
      )
    )[1]::text::bigint
  END AS legacy_count,
  contract_count,
  CASE
    WHEN legacy_rel IS NULL THEN 'NO_LEGACY_TABLE'
    WHEN contract_count >= (
      xpath(
        '/row/cnt/text()',
        query_to_xml('SELECT COUNT(*) AS cnt FROM public.workflow_runs', false, true, '')
      )
    )[1]::text::bigint THEN 'OK'
    ELSE 'MISMATCH'
  END AS status
FROM workflow_runs_check;

WITH workflow_steps_check AS (
  SELECT
    to_regclass('public.workflow_steps') AS legacy_rel,
    (SELECT COUNT(*) FROM public.run_steps) AS contract_count
)
SELECT
  'workflow_steps -> run_steps' AS migration,
  CASE
    WHEN legacy_rel IS NULL THEN 0::bigint
    ELSE (
      xpath(
        '/row/cnt/text()',
        query_to_xml('SELECT COUNT(*) AS cnt FROM public.workflow_steps', false, true, '')
      )
    )[1]::text::bigint
  END AS legacy_count,
  contract_count,
  CASE
    WHEN legacy_rel IS NULL THEN 'NO_LEGACY_TABLE'
    WHEN contract_count >= (
      xpath(
        '/row/cnt/text()',
        query_to_xml('SELECT COUNT(*) AS cnt FROM public.workflow_steps', false, true, '')
      )
    )[1]::text::bigint THEN 'OK'
    ELSE 'MISMATCH'
  END AS status
FROM workflow_steps_check;

WITH connectors_check AS (
  SELECT
    to_regclass('public.connectors') AS legacy_rel,
    (SELECT COUNT(*) FROM public.connected_systems) AS contract_count
)
SELECT
  'connectors -> connected_systems' AS migration,
  CASE
    WHEN legacy_rel IS NULL THEN 0::bigint
    ELSE (
      xpath(
        '/row/cnt/text()',
        query_to_xml('SELECT COUNT(*) AS cnt FROM public.connectors', false, true, '')
      )
    )[1]::text::bigint
  END AS legacy_count,
  contract_count,
  CASE
    WHEN legacy_rel IS NULL THEN 'NO_LEGACY_TABLE'
    WHEN contract_count >= (
      xpath(
        '/row/cnt/text()',
        query_to_xml('SELECT COUNT(*) AS cnt FROM public.connectors', false, true, '')
      )
    )[1]::text::bigint THEN 'OK'
    ELSE 'MISMATCH'
  END AS status
FROM connectors_check;

WITH operators_check AS (
  SELECT
    to_regclass('public.operators') AS legacy_rel,
    (SELECT COUNT(*) FROM public.agents) AS contract_count
)
SELECT
  'operators -> agents' AS migration,
  CASE
    WHEN legacy_rel IS NULL THEN 0::bigint
    ELSE (
      xpath(
        '/row/cnt/text()',
        query_to_xml('SELECT COUNT(*) AS cnt FROM public.operators', false, true, '')
      )
    )[1]::text::bigint
  END AS legacy_count,
  contract_count,
  CASE
    WHEN legacy_rel IS NULL THEN 'NO_LEGACY_TABLE'
    WHEN contract_count >= (
      xpath(
        '/row/cnt/text()',
        query_to_xml('SELECT COUNT(*) AS cnt FROM public.operators', false, true, '')
      )
    )[1]::text::bigint THEN 'OK'
    ELSE 'MISMATCH'
  END AS status
FROM operators_check;

-- 3. SKIPPED ROWS
SELECT 
  details->>'legacy_table' AS legacy_table,
  details->>'reason' AS skip_reason,
  COUNT(*) AS skipped_count
FROM public.audit_logs
WHERE action = 'legacy_backfill_skipped'
GROUP BY details->>'legacy_table', details->>'reason'
ORDER BY skipped_count DESC;

-- 4. ORPHAN CHECK: Runs without valid workflow FK
SELECT COUNT(*) AS orphan_runs
FROM public.runs r
WHERE r.workflow_id IS NOT NULL 
  AND NOT EXISTS (SELECT 1 FROM public.workflows w WHERE w.id = r.workflow_id);

-- 5. ORPHAN CHECK: Run steps without valid run FK
SELECT COUNT(*) AS orphan_steps
FROM public.run_steps rs
WHERE NOT EXISTS (SELECT 1 FROM public.runs r WHERE r.id = rs.run_id);

-- 6. STATUS DISTRIBUTION
SELECT 'agents' AS table_name, status, COUNT(*) FROM public.agents GROUP BY status
UNION ALL
SELECT 'workflows', status, COUNT(*) FROM public.workflows GROUP BY status
UNION ALL
SELECT 'runs', status, COUNT(*) FROM public.runs GROUP BY status
UNION ALL
SELECT 'connected_systems', status, COUNT(*) FROM public.connected_systems GROUP BY status;
