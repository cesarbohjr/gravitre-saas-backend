-- Activate core billing tables in the ACTIVE migrations directory.
--
-- billing_plans and org_billing previously existed only under
-- supabase/migrations/legacy/ (phase16_billing), which `supabase db push` does
-- not apply, so the live project was missing them (org_billing returned
-- PGRST205). This recreates them from the legacy definitions (exact source of
-- truth) plus RLS.
--
-- billing_events is NOT redefined from legacy: it already has an applied active
-- migration (20260427000100_billing_events_demo.sql) with the richer
-- action/status/updated_at schema the code writes, plus RLS. It is included here
-- only as a defensive CREATE TABLE IF NOT EXISTS (no-op where it exists) using
-- that current shape, so this migration is self-consistent in a fresh project.
--
-- Safe to re-run: every statement is IF NOT EXISTS / DROP POLICY IF EXISTS.

-- billing_plans (global config) ------------------------------------------------
CREATE TABLE IF NOT EXISTS public.billing_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name text NOT NULL,
  price_usd numeric(10,2),
  agents_limit int,
  workflows_limit int,
  environments_limit int,
  ai_credits_included int NOT NULL DEFAULT 0,
  workflow_runs_included int NOT NULL DEFAULT 0,
  features jsonb NOT NULL DEFAULT '{}'::jsonb,
  overage_rates jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- org_billing (per-tenant; FK to billing_plans.code, so create plans first) -----
CREATE TABLE IF NOT EXISTS public.org_billing (
  org_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
  stripe_customer_id text,
  stripe_subscription_id text,
  stripe_price_id text,
  plan_code text REFERENCES public.billing_plans(code) ON DELETE SET NULL,
  billing_status text NOT NULL DEFAULT 'trialing',
  current_period_end timestamptz,
  cancel_at_period_end boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- billing_events (current/active shape; no-op where already present) ------------
CREATE TABLE IF NOT EXISTS public.billing_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  action text,
  event_type text,
  status text NOT NULL DEFAULT 'success',
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- RLS --------------------------------------------------------------------------
-- billing_plans: global config -> public read (no org filter). Writes are
-- service-role only (which bypasses RLS); no write policy.
ALTER TABLE public.billing_plans ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "billing_plans_public_read" ON public.billing_plans;
CREATE POLICY "billing_plans_public_read"
  ON public.billing_plans
  FOR SELECT
  USING (true);

-- org_billing: tenant isolation via organization_members (same as model_calls).
ALTER TABLE public.org_billing ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "org_billing_tenant_isolation" ON public.org_billing;
CREATE POLICY "org_billing_tenant_isolation"
  ON public.org_billing
  FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid()
    )
  );

-- billing_events: tenant isolation via organization_members. (The active demo
-- migration also adds a FOR ALL org-scope policy; permissive policies combine.)
ALTER TABLE public.billing_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "billing_events_tenant_isolation" ON public.billing_events;
CREATE POLICY "billing_events_tenant_isolation"
  ON public.billing_events
  FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid()
    )
  );
