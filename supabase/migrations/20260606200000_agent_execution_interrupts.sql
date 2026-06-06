-- STA-108: Human-in-the-loop interrupt channel (pause/cancel before next tool/step)

CREATE TABLE IF NOT EXISTS public.agent_execution_interrupts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  target_type text NOT NULL CHECK (target_type IN ('agent_job', 'workflow_run', 'operator_session')),
  target_id uuid NOT NULL,
  signal text NOT NULL CHECK (signal IN ('pause', 'cancel')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'acknowledged', 'expired')),
  source text NOT NULL DEFAULT 'ui' CHECK (source IN ('ui', 'slack', 'api')),
  requested_by uuid,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  acknowledged_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_agent_interrupts_org_target
  ON public.agent_execution_interrupts (org_id, target_type, target_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_interrupts_pending_unique
  ON public.agent_execution_interrupts (org_id, target_type, target_id)
  WHERE status = 'pending';

ALTER TABLE public.agent_jobs DROP CONSTRAINT IF EXISTS agent_jobs_status_check;
ALTER TABLE public.agent_jobs
  ADD CONSTRAINT agent_jobs_status_check
  CHECK (status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled'));
