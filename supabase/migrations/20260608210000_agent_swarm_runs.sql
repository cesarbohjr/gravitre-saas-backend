-- STA-119: Multi-agent swarm coordinator — parent spawns scoped sub-agents, council aggregates

CREATE TABLE IF NOT EXISTS public.agent_swarm_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  parent_agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  objective text NOT NULL,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'running', 'aggregating', 'completed', 'failed', 'cancelled')),
  decision_method text NOT NULL DEFAULT 'majority_vote'
    CHECK (decision_method IN ('majority_vote', 'unanimous', 'weighted_vote', 'chair_decides')),
  council_session_id text,
  final_recommendation text,
  final_confidence double precision,
  aggregate_result jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_message text,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_agent_swarm_runs_org_created
  ON public.agent_swarm_runs (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_swarm_runs_org_status
  ON public.agent_swarm_runs (org_id, status);

CREATE TABLE IF NOT EXISTS public.agent_swarm_subtasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  swarm_run_id uuid NOT NULL REFERENCES public.agent_swarm_runs(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  task_prompt text NOT NULL,
  scoped_tools jsonb NOT NULL DEFAULT '[]'::jsonb,
  sort_order int NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'queued', 'running', 'completed', 'failed', 'cancelled')),
  agent_job_id uuid REFERENCES public.agent_jobs(id) ON DELETE SET NULL,
  result jsonb,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_agent_swarm_subtasks_swarm
  ON public.agent_swarm_subtasks (swarm_run_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_agent_swarm_subtasks_job
  ON public.agent_swarm_subtasks (agent_job_id);

ALTER TABLE public.agent_swarm_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_swarm_subtasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "agent_swarm_runs_tenant" ON public.agent_swarm_runs;
CREATE POLICY "agent_swarm_runs_tenant"
  ON public.agent_swarm_runs
  FOR SELECT
  USING (
    org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
  );

DROP POLICY IF EXISTS "agent_swarm_subtasks_tenant" ON public.agent_swarm_subtasks;
CREATE POLICY "agent_swarm_subtasks_tenant"
  ON public.agent_swarm_subtasks
  FOR SELECT
  USING (
    org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
  );

COMMENT ON TABLE public.agent_swarm_runs IS
  'Parent-agent swarm session; sub-agents run in parallel then council aggregates (STA-119).';
COMMENT ON TABLE public.agent_swarm_subtasks IS
  'Scoped sub-agent work unit within a swarm run; linked to agent_jobs queue.';
