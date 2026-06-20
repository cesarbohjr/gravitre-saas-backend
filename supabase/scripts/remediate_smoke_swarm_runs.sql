-- STA-263: Force-fail pre-trust-fix smoke swarm runs stuck in aggregating.
-- Decision: council never completed → no valid recommendation; mark runs failed (not relabeled).
-- Safe to re-run: only touches matching aggregating smoke rows.

BEGIN;

UPDATE public.agent_swarm_subtasks st
SET
  updated_at = now(),
  result = COALESCE(st.result, '{}'::jsonb) || jsonb_build_object(
    'remediationNote',
    'Pre-trust-fix subtask output; council never aggregated (STA-263 force-fail).'
  )
FROM public.agent_swarm_runs r
WHERE st.swarm_run_id = r.id
  AND r.org_id = '00000000-0000-0000-0000-000000000001'::uuid
  AND r.status = 'aggregating'
  AND r.objective ILIKE '%Tier5 smoke swarm%';

UPDATE public.agent_swarm_runs
SET
  status = 'failed',
  error_message = 'Swarm incomplete: council aggregation never finished (pre-trust-fix smoke run; force-failed STA-263).',
  execution_verified = false,
  updated_at = now(),
  completed_at = COALESCE(completed_at, now())
WHERE org_id = '00000000-0000-0000-0000-000000000001'::uuid
  AND status = 'aggregating'
  AND objective ILIKE '%Tier5 smoke swarm%';

COMMIT;

-- Verify (run separately if needed):
-- SELECT id, status, error_message, execution_verified, objective
-- FROM public.agent_swarm_runs
-- WHERE org_id = '00000000-0000-0000-0000-000000000001'
--   AND objective ILIKE '%Tier5 smoke swarm%';
