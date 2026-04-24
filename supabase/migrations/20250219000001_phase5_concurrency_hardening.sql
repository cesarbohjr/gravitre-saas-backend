-- Phase 5: Prevent multiple active execute runs per workflow
-- Active = pending_approval or running
CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_runs_active_unique
  ON public.workflow_runs(org_id, workflow_id)
  WHERE run_type = 'execute' AND status IN ('pending_approval', 'running');
