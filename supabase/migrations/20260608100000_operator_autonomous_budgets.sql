-- STA-109: Autonomous run budgets (actions, tokens, spend/day) per operator

ALTER TABLE public.operators
  ADD COLUMN IF NOT EXISTS auto_run_max_actions_per_day integer
    CHECK (auto_run_max_actions_per_day IS NULL OR auto_run_max_actions_per_day >= 0),
  ADD COLUMN IF NOT EXISTS auto_run_max_tokens_per_day integer
    CHECK (auto_run_max_tokens_per_day IS NULL OR auto_run_max_tokens_per_day >= 0),
  ADD COLUMN IF NOT EXISTS auto_run_max_spend_usd_per_day numeric(12, 4)
    CHECK (auto_run_max_spend_usd_per_day IS NULL OR auto_run_max_spend_usd_per_day >= 0);

CREATE TABLE IF NOT EXISTS public.operator_autonomous_usage_daily (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  operator_id uuid NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
  usage_date date NOT NULL,
  action_count integer NOT NULL DEFAULT 0 CHECK (action_count >= 0),
  token_count integer NOT NULL DEFAULT 0 CHECK (token_count >= 0),
  spend_usd numeric(12, 4) NOT NULL DEFAULT 0 CHECK (spend_usd >= 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, operator_id, usage_date)
);

CREATE INDEX IF NOT EXISTS idx_operator_autonomous_usage_daily_lookup
  ON public.operator_autonomous_usage_daily (org_id, operator_id, usage_date DESC);

ALTER TABLE public.operator_autonomous_usage_daily ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "operator_autonomous_usage_daily_org" ON public.operator_autonomous_usage_daily;
CREATE POLICY "operator_autonomous_usage_daily_org"
  ON public.operator_autonomous_usage_daily FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));
