-- PR #605: non-mutating, aggregate-only run-store reconciliation.
-- Run against a project whose binding to the deployment has been attested.
-- Deliberately excludes user/org IDs, provider payloads and individual run IDs.
-- The mirror's status translation is copied from
-- 20261001162827_verified_write_lifecycle_states.sql; update both together
-- after an approved contract migration. Zero mutations.
WITH joined AS (
  SELECT w.id AS workflow_run_id, r.id AS contract_run_id,
         w.status AS workflow_status, r.status AS contract_status,
         w.run_type,
         r.metadata ->> 'mirrored_by' AS mirror_source,
         CASE lower(coalesce(w.status, ''))
           WHEN 'pending_approval' THEN 'needs_approval'
           WHEN 'awaiting_approval' THEN 'needs_approval'
           WHEN 'partial_success' THEN 'completed'
           WHEN 'verifying' THEN 'running'
           WHEN 'verification_inconclusive' THEN 'failed'
           WHEN 'error' THEN 'failed'
           ELSE lower(coalesce(w.status, 'running'))
         END AS expected_status
  FROM public.workflow_runs w
  FULL OUTER JOIN public.runs r ON r.id = w.id
)
SELECT CASE
         WHEN workflow_run_id IS NULL THEN 'runs_only_not_necessarily_orphan'
         WHEN contract_run_id IS NULL THEN 'workflow_runs_only_needs_investigation'
         WHEN contract_status IS NOT DISTINCT FROM expected_status THEN 'aligned_after_translation'
         WHEN workflow_status = 'flagged_for_review' THEN 'unmapped_distinct_review_status'
         ELSE 'divergent_after_translation'
       END AS classification,
       coalesce(workflow_status, '<none>') AS workflow_status,
       coalesce(contract_status, '<none>') AS contract_status,
       coalesce(expected_status, '<none>') AS expected_status,
       coalesce(mirror_source, '<none>') AS mirror_source,
       count(*)::bigint AS records
FROM joined
GROUP BY 1,2,3,4,5
ORDER BY 1,records DESC;

-- Guardrail notes:
-- pending_approval -> needs_approval is intentional.
-- partial_success -> completed is the *existing coarse contract* but may
-- misrepresent partial success to consumers; do not silently relabel history.
-- flagged_for_review is deliberately neither verified nor failed; runs.status
-- has no corresponding allowed value, so the current trigger can reject it.
-- In-place UPDATE would emit triggers and outbox events and is prohibited in
-- this audit. Before migration, inspect run types, timestamps, grants, consumers,
-- and future-compatible status vocabulary. Use a preview/dry-run reconciliation
-- with per-org authorization, then certified migration with rollback.
