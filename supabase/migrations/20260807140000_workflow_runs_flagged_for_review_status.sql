-- Phase 4 — distinct terminal for degenerate / low-information batch outputs.
-- Different from completed, partial_success, and failed. UI surfacing lands in Phase 6.
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
      'partial_success',
      'flagged_for_review'
    )
  );

COMMENT ON CONSTRAINT workflow_runs_status_check ON public.workflow_runs IS
  'Terminal statuses include partial_success (honesty) and flagged_for_review (batch degeneracy).';
