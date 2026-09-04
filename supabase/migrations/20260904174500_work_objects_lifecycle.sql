-- WorkObject lifecycle spine: durable cross-run business entity continuity.

CREATE TABLE IF NOT EXISTS public.work_objects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  object_type text NOT NULL CHECK (
    object_type IN (
      'opportunity',
      'campaign',
      'candidate',
      'financial_issue',
      'ticket',
      'contract_matter',
      'incident',
      'vulnerability',
      'vendor',
      'feature',
      'issue_pr',
      'objective',
      'other'
    )
  ),
  department text NOT NULL DEFAULT 'operations',
  title text NOT NULL,
  objective text,
  owner_user_id text,
  status text NOT NULL DEFAULT 'identified' CHECK (
    status IN (
      'identified',
      'planned',
      'in_progress',
      'awaiting_approval',
      'blocked',
      'completed',
      'failed',
      'archived'
    )
  ),
  priority text NOT NULL DEFAULT 'medium' CHECK (
    priority IN ('low', 'medium', 'high', 'critical')
  ),
  external_entity_type text,
  external_entity_id text,
  anchor_conversation_id text,
  systems_involved jsonb NOT NULL DEFAULT '[]'::jsonb,
  agents_involved jsonb NOT NULL DEFAULT '[]'::jsonb,
  plan jsonb NOT NULL DEFAULT '{}'::jsonb,
  human_approvals jsonb NOT NULL DEFAULT '{}'::jsonb,
  outcome jsonb NOT NULL DEFAULT '{}'::jsonb,
  roi jsonb NOT NULL DEFAULT '{}'::jsonb,
  business_outcome_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  last_activity_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.work_object_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  work_object_id uuid NOT NULL REFERENCES public.work_objects(id) ON DELETE CASCADE,
  run_id uuid REFERENCES public.workflow_runs(id) ON DELETE SET NULL,
  business_outcome_id uuid REFERENCES public.workflow_runs(id) ON DELETE SET NULL,
  conversation_id text,
  event_type text NOT NULL DEFAULT 'action_attributed',
  action_name text,
  action_status text,
  system_name text,
  agent_id text,
  human_approval jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  outcome jsonb NOT NULL DEFAULT '{}'::jsonb,
  roi jsonb NOT NULL DEFAULT '{}'::jsonb,
  audit_ref jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_work_objects_org_last_activity
  ON public.work_objects (org_id, last_activity_at DESC);

CREATE INDEX IF NOT EXISTS idx_work_objects_org_type_status
  ON public.work_objects (org_id, object_type, status);

CREATE UNIQUE INDEX IF NOT EXISTS idx_work_objects_entity_anchor
  ON public.work_objects (org_id, object_type, external_entity_type, external_entity_id)
  WHERE external_entity_type IS NOT NULL AND external_entity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_work_object_events_org_object_created
  ON public.work_object_events (org_id, work_object_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_work_object_events_run
  ON public.work_object_events (run_id);

ALTER TABLE public.work_objects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.work_object_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "work_objects_org" ON public.work_objects;
CREATE POLICY "work_objects_org"
  ON public.work_objects FOR ALL
  USING (
    org_id = (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
      LIMIT 1
    )
  );

DROP POLICY IF EXISTS "work_object_events_org" ON public.work_object_events;
CREATE POLICY "work_object_events_org"
  ON public.work_object_events FOR ALL
  USING (
    org_id = (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
      LIMIT 1
    )
  );
