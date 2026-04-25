-- ============================================
-- GRAVITRE BACKFILL VERIFICATION
-- Run this AFTER migration to validate parity
-- Read-only: no modifications
-- ============================================

-- NOTE:
-- This script is read-only and assumes the listed legacy tables exist:
-- workflow_defs, workflow_runs, workflow_steps, connectors, operators.
-- If any of those legacy tables are missing in an environment, comment out the
-- corresponding comparison query before running in Supabase SQL editor.

-- 1. ROW COUNTS
SELECT 'workflows' AS table_name, COUNT(*) AS row_count FROM workflows
UNION ALL
SELECT 'runs', COUNT(*) FROM runs
UNION ALL
SELECT 'run_steps', COUNT(*) FROM run_steps
UNION ALL
SELECT 'connected_systems', COUNT(*) FROM connected_systems
UNION ALL
SELECT 'agents', COUNT(*) FROM agents
UNION ALL
SELECT 'approvals', COUNT(*) FROM approvals
UNION ALL
SELECT 'organizations', COUNT(*) FROM organizations
UNION ALL
SELECT 'users', COUNT(*) FROM users;

-- 2. LEGACY VS CONTRACT COUNTS
SELECT 
  'workflow_defs → workflows' AS migration,
  (SELECT COUNT(*) FROM workflow_defs) AS legacy_count,
  (SELECT COUNT(*) FROM workflows) AS contract_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM workflows) >= (SELECT COUNT(*) FROM workflow_defs) 
    THEN 'OK' 
    ELSE 'MISMATCH' 
  END AS status;

SELECT 
  'workflow_runs → runs' AS migration,
  (SELECT COUNT(*) FROM workflow_runs) AS legacy_count,
  (SELECT COUNT(*) FROM runs) AS contract_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM runs) >= (SELECT COUNT(*) FROM workflow_runs) 
    THEN 'OK' 
    ELSE 'MISMATCH' 
  END AS status;

SELECT 
  'workflow_steps → run_steps' AS migration,
  (SELECT COUNT(*) FROM workflow_steps) AS legacy_count,
  (SELECT COUNT(*) FROM run_steps) AS contract_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM run_steps) >= (SELECT COUNT(*) FROM workflow_steps) 
    THEN 'OK' 
    ELSE 'MISMATCH' 
  END AS status;

SELECT 
  'connectors → connected_systems' AS migration,
  (SELECT COUNT(*) FROM connectors) AS legacy_count,
  (SELECT COUNT(*) FROM connected_systems) AS contract_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM connected_systems) >= (SELECT COUNT(*) FROM connectors) 
    THEN 'OK' 
    ELSE 'MISMATCH' 
  END AS status;

SELECT 
  'operators → agents' AS migration,
  (SELECT COUNT(*) FROM operators) AS legacy_count,
  (SELECT COUNT(*) FROM agents) AS contract_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM agents) >= (SELECT COUNT(*) FROM operators) 
    THEN 'OK' 
    ELSE 'MISMATCH' 
  END AS status;

-- 3. SKIPPED ROWS
SELECT 
  details->>'legacy_table' AS legacy_table,
  details->>'reason' AS skip_reason,
  COUNT(*) AS skipped_count
FROM audit_logs
WHERE action = 'legacy_backfill_skipped'
GROUP BY details->>'legacy_table', details->>'reason'
ORDER BY skipped_count DESC;

-- 4. ORPHAN CHECK: Runs without valid workflow FK
SELECT COUNT(*) AS orphan_runs
FROM runs r
WHERE r.workflow_id IS NOT NULL 
  AND NOT EXISTS (SELECT 1 FROM workflows w WHERE w.id = r.workflow_id);

-- 5. ORPHAN CHECK: Run steps without valid run FK
SELECT COUNT(*) AS orphan_steps
FROM run_steps rs
WHERE NOT EXISTS (SELECT 1 FROM runs r WHERE r.id = rs.run_id);

-- 6. STATUS DISTRIBUTION
SELECT 'agents' AS table_name, status, COUNT(*) FROM agents GROUP BY status
UNION ALL
SELECT 'workflows', status, COUNT(*) FROM workflows GROUP BY status
UNION ALL
SELECT 'runs', status, COUNT(*) FROM runs GROUP BY status
UNION ALL
SELECT 'connected_systems', status, COUNT(*) FROM connected_systems GROUP BY status;
