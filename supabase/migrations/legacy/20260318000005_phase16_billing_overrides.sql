-- Phase 16: Org billing overrides (enterprise contracts)

CREATE TABLE IF NOT EXISTS public.org_billing_overrides (
  org_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
  agents_limit int,
  workflows_limit int,
  environments_limit int,
  ai_credits_included int,
  workflow_runs_included int,
  approvals text,
  audit_logs text,
  versioning text,
  advanced_connectors boolean,
  rbac boolean,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
