-- STA-106: Policy-gated auto-execute mode per operator

ALTER TABLE public.operators
  ADD COLUMN IF NOT EXISTS execution_mode text NOT NULL DEFAULT 'plan_only'
    CHECK (execution_mode IN ('plan_only', 'auto_with_approval', 'auto_trusted_scopes')),
  ADD COLUMN IF NOT EXISTS auto_execute_trusted_scopes jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS auto_execute_enabled_at timestamptz,
  ADD COLUMN IF NOT EXISTS auto_execute_enabled_by uuid REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_operators_execution_mode
  ON public.operators(org_id, execution_mode)
  WHERE execution_mode <> 'plan_only';
