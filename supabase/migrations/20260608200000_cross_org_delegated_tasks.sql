-- STA-118: Delegate sub-tasks to external Gravitre orgs with status sync back to delegator

CREATE TABLE IF NOT EXISTS public.cross_org_delegated_tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  partnership_id uuid NOT NULL REFERENCES public.org_b2b_partnerships(id) ON DELETE CASCADE,
  delegator_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  delegate_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  delegator_agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  delegate_agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  delegate_agent_job_id uuid REFERENCES public.agent_jobs(id) ON DELETE SET NULL,
  title text NOT NULL,
  instructions text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  parent_reference jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending_delegate'
    CHECK (status IN (
      'pending_delegate',
      'accepted',
      'in_progress',
      'completed',
      'rejected',
      'cancelled',
      'failed'
    )),
  result jsonb,
  status_message text,
  sync_version integer NOT NULL DEFAULT 1,
  delegator_user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  delegate_user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  accepted_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  rejected_at timestamptz,
  cancelled_at timestamptz,
  status_synced_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cross_org_delegated_tasks_delegator
  ON public.cross_org_delegated_tasks (delegator_org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cross_org_delegated_tasks_delegate
  ON public.cross_org_delegated_tasks (delegate_org_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cross_org_delegated_tasks_partnership
  ON public.cross_org_delegated_tasks (partnership_id);

ALTER TABLE public.cross_org_delegated_tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "cross_org_delegated_tasks_tenant" ON public.cross_org_delegated_tasks;
CREATE POLICY "cross_org_delegated_tasks_tenant"
  ON public.cross_org_delegated_tasks
  FOR SELECT
  USING (
    delegator_org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
    OR delegate_org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
  );

COMMENT ON TABLE public.cross_org_delegated_tasks IS
  'Cross-org delegated sub-tasks; delegate org updates status and result sync back to delegator (STA-118).';
