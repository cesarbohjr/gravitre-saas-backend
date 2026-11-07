-- PR605 run-status v2 historical reconciliation: READ ONLY.
-- Before executing against any environment, attest the DB project ref.
-- Deliberately aggregates without exposing IDs, org IDs, secrets or user data.
-- Treat each row of an approved future backfill as CAS-guarded, not a bulk UPDATE.
WITH pairs AS (
 SELECT w.id AS workflow_id, r.id AS contract_id,
        w.status AS workflow_status, r.status AS contract_status,
        w.run_type,
        r.metadata ->> 'status_contract_version' AS contract_version,
        r.metadata ->> 'execution_lifecycle' AS projected_lifecycle,
        CASE lower(coalesce(w.status,'')) 
          WHEN 'pending' THEN 'queued'
          WHEN 'pending_approval' THEN 'needs_approval'
          WHEN 'awaiting_approval' THEN 'needs_approval'
          WHEN 'success' THEN 'completed'
          WHEN 'verifying' THEN 'running'
          WHEN 'verification_inconclusive' THEN 'failed'
          WHEN 'error' THEN 'failed'
          WHEN 'canceled' THEN 'cancelled'
          ELSE lower(w.status)
        END AS expected_v2
 FROM public.workflow_runs w
 FULL JOIN public.runs r ON r.id=w.id
), categorized AS (
 SELECT CASE
  WHEN workflow_id IS NULL THEN 'runs_only_different_domain_possible'
  WHEN contract_id IS NULL THEN 'missing_contract_projection'
  WHEN contract_status IS NOT DISTINCT FROM expected_v2 THEN 'matches_v2'
  ELSE 'needs_authorized_reconciliation'
 END AS category,
 workflow_status, contract_status, expected_v2,
 coalesce(contract_version,'unknown') AS contract_version,
 coalesce(projected_lifecycle,'unknown') AS projected_lifecycle,
 coalesce(run_type,'unknown') AS run_type
 FROM pairs
)
SELECT category,coalesce(workflow_status,'<none>') workflow_status,
 coalesce(contract_status,'<none>') contract_status,
 coalesce(expected_v2,'<none>') expected_v2,
 contract_version, projected_lifecycle, run_type, count(*)::bigint n
FROM categorized
GROUP BY 1,2,3,4,5,6,7
ORDER BY category,n DESC;

-- NOT APPROVED FOR EXECUTION: no UPDATE/INSERT is part of this file.
-- A later reconciler requires:
--   1. explicit org scope + approved whitelist of run IDs;
--   2. source and contract status compare-and-set conditions;
--   3. v2 migration applied and all consumers certified;
--   4. idempotent audit record, durable reconcile outcome, rollback checkpoint;
--   5. no duplicate workflow terminal outbox events;
--   6. measured post-run status parity and UI/analytics verification.
