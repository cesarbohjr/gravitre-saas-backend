-- Canonical connector-write lifecycle truth.
-- A provider accepting a mutation is not a terminal success. Runs stay
-- non-terminal while source-of-record verification is in flight and may end
-- explicitly inconclusive without ever emitting completed.
ALTER TABLE public.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_status_check;

ALTER TABLE public.workflow_runs
  ADD CONSTRAINT workflow_runs_status_check
  CHECK (
    status IN (
      'running',
      'verifying',
      'completed',
      'failed',
      'cancelled',
      'pending_approval',
      'awaiting_approval',
      'paused',
      'partial_success',
      'flagged_for_review',
      'verification_inconclusive'
    )
  );

COMMENT ON CONSTRAINT workflow_runs_status_check ON public.workflow_runs IS
  'Write lifecycle: provider acceptance may transition to verifying; completed requires source-of-record proof; verification_inconclusive is terminal non-success.';
