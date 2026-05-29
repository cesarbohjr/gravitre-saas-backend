-- Durable async agent/operator job queue (additive; the synchronous operator
-- endpoint is unchanged). A job is enqueued (status=queued), claimed by the
-- in-process worker (running), then completed/failed; cancel/retry supported.

CREATE TABLE IF NOT EXISTS public.agent_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  session_id uuid,
  kind text NOT NULL DEFAULT 'operator_task',
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
  environment text NOT NULL DEFAULT 'production',
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  result jsonb,
  error text,
  attempts int NOT NULL DEFAULT 0,
  max_attempts int NOT NULL DEFAULT 3,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  finished_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_jobs_status_created
  ON public.agent_jobs (status, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_org_created
  ON public.agent_jobs (org_id, created_at DESC);

ALTER TABLE public.agent_jobs ENABLE ROW LEVEL SECURITY;

-- Tenant-isolated reads (same pattern as model_calls / guardrail_events). Writes
-- come from the service role (worker + endpoints), which bypasses RLS.
DROP POLICY IF EXISTS "agent_jobs_tenant_isolation" ON public.agent_jobs;
CREATE POLICY "agent_jobs_tenant_isolation"
  ON public.agent_jobs
  FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid()
    )
  );
