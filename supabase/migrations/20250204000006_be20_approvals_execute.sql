-- BE-20: Approvals + constrained execute (Option C: per-workflow + org default)
-- Authority: docs/phase-2/BE-20_APPROVALS_EXECUTE_PLAN.md
-- Requires: workflow_defs, workflow_runs, workflow_steps, audit_events, organizations, organization_members

-- approval_policies: per-workflow or org default (workflow_id NULL)
CREATE TABLE public.approval_policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid REFERENCES public.workflow_defs(id) ON DELETE CASCADE,
  run_types text[] NOT NULL DEFAULT '{execute}',
  required_approvals int NOT NULL DEFAULT 1,
  approver_roles text[] NOT NULL DEFAULT '{admin}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  UNIQUE (org_id, workflow_id)
);

CREATE INDEX idx_approval_policies_org_id ON public.approval_policies(org_id);
CREATE INDEX idx_approval_policies_workflow_id ON public.approval_policies(workflow_id);

-- run_approvals: one decision per approver per run
CREATE TABLE public.run_approvals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES public.workflow_runs(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  approver_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status text NOT NULL CHECK (status IN ('approved', 'rejected')),
  comment text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (run_id, approver_id)
);

CREATE INDEX idx_run_approvals_run_id ON public.run_approvals(run_id);
CREATE INDEX idx_run_approvals_org_id ON public.run_approvals(org_id);

-- Extend workflow_runs: add pending_approval to status, approval columns
ALTER TABLE public.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_status_check;

ALTER TABLE public.workflow_runs
  ADD CONSTRAINT workflow_runs_status_check
  CHECK (status IN ('running', 'completed', 'failed', 'cancelled', 'pending_approval'));

ALTER TABLE public.workflow_runs
  ADD COLUMN IF NOT EXISTS approval_status text
  CHECK (approval_status IS NULL OR approval_status IN ('pending_approval', 'approved', 'rejected'));

ALTER TABLE public.workflow_runs
  ADD COLUMN IF NOT EXISTS required_approvals int;

ALTER TABLE public.workflow_runs
  ADD COLUMN IF NOT EXISTS approver_roles text[];

-- RLS for new tables
ALTER TABLE public.approval_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.run_approvals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "approval_policies_org"
  ON public.approval_policies FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "run_approvals_org"
  ON public.run_approvals FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));
