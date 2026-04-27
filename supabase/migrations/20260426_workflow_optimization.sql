-- Workflow optimization schema (idempotent, non-destructive)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.workflow_health_snapshots (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid REFERENCES public.workflows(id) ON DELETE CASCADE,
  score integer NOT NULL,
  dimensions jsonb NOT NULL DEFAULT '{}'::jsonb,
  recorded_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.workflow_health_snapshots
  ADD COLUMN IF NOT EXISTS workflow_id uuid REFERENCES public.workflows(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS score integer,
  ADD COLUMN IF NOT EXISTS dimensions jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS recorded_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS public.optimization_recommendations (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid REFERENCES public.workflows(id) ON DELETE CASCADE,
  issue text NOT NULL,
  evidence text,
  suggested_change jsonb NOT NULL DEFAULT '{}'::jsonb,
  estimated_impact jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric,
  risk_level text,
  status text NOT NULL DEFAULT 'open',
  affected_nodes text[] NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.optimization_recommendations
  ADD COLUMN IF NOT EXISTS workflow_id uuid REFERENCES public.workflows(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS issue text,
  ADD COLUMN IF NOT EXISTS evidence text,
  ADD COLUMN IF NOT EXISTS suggested_change jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS estimated_impact jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS confidence numeric,
  ADD COLUMN IF NOT EXISTS risk_level text,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'open',
  ADD COLUMN IF NOT EXISTS affected_nodes text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'optimization_recommendations_status_check'
      AND conrelid = 'public.optimization_recommendations'::regclass
  ) THEN
    ALTER TABLE public.optimization_recommendations
      ADD CONSTRAINT optimization_recommendations_status_check
      CHECK (status IN ('open', 'applied', 'dismissed'));
  END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.workflow_ab_tests (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid REFERENCES public.workflows(id) ON DELETE CASCADE,
  version_a integer NOT NULL,
  version_b integer NOT NULL,
  traffic_split jsonb NOT NULL DEFAULT '{}'::jsonb,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.workflow_ab_tests
  ADD COLUMN IF NOT EXISTS workflow_id uuid REFERENCES public.workflows(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS version_a integer,
  ADD COLUMN IF NOT EXISTS version_b integer,
  ADD COLUMN IF NOT EXISTS traffic_split jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'workflow_ab_tests_status_check'
      AND conrelid = 'public.workflow_ab_tests'::regclass
  ) THEN
    ALTER TABLE public.workflow_ab_tests
      ADD CONSTRAINT workflow_ab_tests_status_check
      CHECK (status IN ('draft', 'running', 'completed', 'cancelled'));
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_workflow_health_org_id ON public.workflow_health_snapshots(org_id);
CREATE INDEX IF NOT EXISTS idx_workflow_health_workflow_id ON public.workflow_health_snapshots(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_health_recorded_at ON public.workflow_health_snapshots(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_optimization_recommendations_org_id ON public.optimization_recommendations(org_id);
CREATE INDEX IF NOT EXISTS idx_optimization_recommendations_workflow_id ON public.optimization_recommendations(workflow_id);
CREATE INDEX IF NOT EXISTS idx_optimization_recommendations_status ON public.optimization_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_workflow_ab_tests_org_id ON public.workflow_ab_tests(org_id);
CREATE INDEX IF NOT EXISTS idx_workflow_ab_tests_workflow_id ON public.workflow_ab_tests(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_ab_tests_status ON public.workflow_ab_tests(status);

ALTER TABLE public.workflow_health_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.optimization_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_ab_tests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "workflow_health_snapshots_org_scope" ON public.workflow_health_snapshots;
CREATE POLICY "workflow_health_snapshots_org_scope"
  ON public.workflow_health_snapshots FOR ALL
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

DROP POLICY IF EXISTS "optimization_recommendations_org_scope" ON public.optimization_recommendations;
CREATE POLICY "optimization_recommendations_org_scope"
  ON public.optimization_recommendations FOR ALL
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

DROP POLICY IF EXISTS "workflow_ab_tests_org_scope" ON public.workflow_ab_tests;
CREATE POLICY "workflow_ab_tests_org_scope"
  ON public.workflow_ab_tests FOR ALL
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

DROP TRIGGER IF EXISTS trg_optimization_recommendations_updated_at ON public.optimization_recommendations;
CREATE TRIGGER trg_optimization_recommendations_updated_at
BEFORE UPDATE ON public.optimization_recommendations
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_workflow_ab_tests_updated_at ON public.workflow_ab_tests;
CREATE TRIGGER trg_workflow_ab_tests_updated_at
BEFORE UPDATE ON public.workflow_ab_tests
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
