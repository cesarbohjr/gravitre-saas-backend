-- Activate billing usage tables in the ACTIVE migrations directory.
--
-- usage_tracking and overage_usage previously existed only under
-- supabase/migrations/legacy/ (phase16_billing + phase16_ai_credit_tokens),
-- which `supabase db push` does not apply. This migration recreates the full,
-- current schema (base columns + the ai_credit_tokens columns) so the tables
-- the billing service writes to are guaranteed to exist.
--
-- Safe to re-run: every statement is IF NOT EXISTS. If the tables already exist
-- (e.g. legacy was applied at some point), this is a no-op.

CREATE TABLE IF NOT EXISTS public.usage_tracking (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  environment text NOT NULL DEFAULT 'production',
  metric_type text NOT NULL CHECK (metric_type IN ('ai_credits', 'workflow_runs', 'operator_usage', 'rag_usage')),
  quantity int NOT NULL DEFAULT 0,
  period_start date NOT NULL,
  period_end date NOT NULL,
  -- ai_credit_tokens columns (legacy phase16_ai_credit_tokens)
  model_name text,
  input_tokens int,
  output_tokens int,
  credits int,
  source text,
  source_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_tracking_org_period
  ON public.usage_tracking(org_id, period_start, period_end, metric_type);

CREATE TABLE IF NOT EXISTS public.overage_usage (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  environment text NOT NULL DEFAULT 'production',
  metric_type text NOT NULL CHECK (metric_type IN ('ai_credits', 'workflow_runs')),
  quantity int NOT NULL DEFAULT 0,
  period_start date NOT NULL,
  period_end date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_overage_usage_org_period
  ON public.overage_usage(org_id, period_start, period_end, metric_type);
