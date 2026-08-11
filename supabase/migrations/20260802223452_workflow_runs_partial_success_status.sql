-- Allow Module A honesty terminals (empty-shell list populate, idempotent finds)
-- to persist as partial_success on workflow_runs. App code has used this status
-- for OutcomeEffect gates; the check constraint previously omitted it so
-- finalize_execution_outcome fanout logged run_persisted=False.
ALTER TABLE public.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_status_check;

ALTER TABLE public.workflow_runs
  ADD CONSTRAINT workflow_runs_status_check
  CHECK (
    status IN (
      'running',
      'completed',
      'failed',
      'cancelled',
      'pending_approval',
      'awaiting_approval',
      'paused',
      'partial_success'
    )
  );

COMMENT ON CONSTRAINT workflow_runs_status_check ON public.workflow_runs IS
  'Terminal statuses include partial_success for unproven/empty-shell mutating honesty.';
