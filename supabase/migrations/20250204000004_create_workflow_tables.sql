-- BE-11: Workflow dry-run + audit. workflow_defs, workflow_runs, workflow_steps, audit_events
-- Authority: docs/phase-1/BE-11_WORKFLOW_DRY_RUN_PLAN.md
-- Requires: organizations, organization_members (BE-00)

-- workflow_defs: stored definitions (read-only from API in Phase 1)
CREATE TABLE public.workflow_defs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  definition jsonb NOT NULL,
  schema_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX idx_workflow_defs_org_id ON public.workflow_defs(org_id);
CREATE INDEX idx_workflow_defs_org_name ON public.workflow_defs(org_id, name);
CREATE UNIQUE INDEX idx_workflow_defs_org_name_version ON public.workflow_defs(org_id, name, schema_version);

-- workflow_runs: one per dry-run or (Phase 2) execute
CREATE TABLE public.workflow_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid REFERENCES public.workflow_defs(id) ON DELETE SET NULL,
  run_type text NOT NULL CHECK (run_type IN ('dry_run', 'execute')),
  status text NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
  triggered_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  definition_snapshot jsonb NOT NULL,
  parameters jsonb,
  run_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  error_message text
);

CREATE INDEX idx_workflow_runs_org_created ON public.workflow_runs(org_id, created_at DESC);
CREATE INDEX idx_workflow_runs_workflow_id ON public.workflow_runs(workflow_id);
CREATE INDEX idx_workflow_runs_run_type ON public.workflow_runs(run_type);

-- workflow_steps: per-step trace; org_id for simple RLS and fast queries
CREATE TABLE public.workflow_steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES public.workflow_runs(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  step_id text NOT NULL,
  step_index int NOT NULL,
  step_name text NOT NULL,
  step_type text NOT NULL,
  status text NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
  input_snapshot jsonb,
  output_snapshot jsonb,
  error_code text,
  error_message text,
  is_retryable boolean DEFAULT false,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_workflow_steps_run_index ON public.workflow_steps(run_id, step_index);
CREATE INDEX idx_workflow_steps_org_id ON public.workflow_steps(org_id);

-- audit_events: workflow-scoped; no PII in metadata
CREATE TABLE public.audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  action text NOT NULL,
  actor_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  resource_type text NOT NULL,
  resource_id uuid NOT NULL,
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_events_org_created ON public.audit_events(org_id, created_at DESC);
CREATE INDEX idx_audit_events_resource ON public.audit_events(resource_type, resource_id);

-- RLS: org-scoped via organization_members
ALTER TABLE public.workflow_defs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workflow_defs_org"
  ON public.workflow_defs FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "workflow_runs_org"
  ON public.workflow_runs FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "workflow_steps_org"
  ON public.workflow_steps FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "audit_events_org"
  ON public.audit_events FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));
