-- STA-139: in-graph approval pause + graph execution statuses on workflow_runs
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
      'paused'
    )
  );
