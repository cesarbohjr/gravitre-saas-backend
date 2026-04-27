-- Goal-based workflows schema (idempotent, non-destructive)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.goals (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  objective text NOT NULL,
  category text,
  priority text,
  frequency text,
  department text,
  success_metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  connected_systems text[] NOT NULL DEFAULT '{}',
  status text NOT NULL DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.goals
  ADD COLUMN IF NOT EXISTS objective text,
  ADD COLUMN IF NOT EXISTS category text,
  ADD COLUMN IF NOT EXISTS priority text,
  ADD COLUMN IF NOT EXISTS frequency text,
  ADD COLUMN IF NOT EXISTS department text,
  ADD COLUMN IF NOT EXISTS success_metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS connected_systems text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'goals_status_check'
      AND conrelid = 'public.goals'::regclass
  ) THEN
    ALTER TABLE public.goals
      ADD CONSTRAINT goals_status_check
      CHECK (status IN ('draft', 'active', 'paused', 'completed', 'cancelled'));
  END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.goal_plans (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  goal_id uuid REFERENCES public.goals(id) ON DELETE CASCADE,
  proposed_steps jsonb NOT NULL DEFAULT '[]'::jsonb,
  required_connectors text[] NOT NULL DEFAULT '{}',
  required_agents uuid[] NOT NULL DEFAULT '{}',
  approval_gates jsonb NOT NULL DEFAULT '[]'::jsonb,
  estimated_impact jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.goal_plans
  ADD COLUMN IF NOT EXISTS goal_id uuid REFERENCES public.goals(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS proposed_steps jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS required_connectors text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS required_agents uuid[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS approval_gates jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS estimated_impact jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_goals_org_id ON public.goals(org_id);
CREATE INDEX IF NOT EXISTS idx_goals_status ON public.goals(status);
CREATE INDEX IF NOT EXISTS idx_goals_created_at ON public.goals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_goal_plans_org_id ON public.goal_plans(org_id);
CREATE INDEX IF NOT EXISTS idx_goal_plans_goal_id ON public.goal_plans(goal_id);
CREATE INDEX IF NOT EXISTS idx_goal_plans_created_at ON public.goal_plans(created_at DESC);

ALTER TABLE public.goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.goal_plans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "goals_org_scope" ON public.goals;
CREATE POLICY "goals_org_scope"
  ON public.goals FOR ALL
  USING (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "goal_plans_org_scope" ON public.goal_plans;
CREATE POLICY "goal_plans_org_scope"
  ON public.goal_plans FOR ALL
  USING (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  );

DROP TRIGGER IF EXISTS trg_goals_updated_at ON public.goals;
CREATE TRIGGER trg_goals_updated_at
BEFORE UPDATE ON public.goals
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_goal_plans_updated_at ON public.goal_plans;
CREATE TRIGGER trg_goal_plans_updated_at
BEFORE UPDATE ON public.goal_plans
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
