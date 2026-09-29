-- Dataset usage bindings for Model Studio / Plays.
-- Extends existing training_datasets; does not create a parallel dataset product.

CREATE TABLE IF NOT EXISTS public.training_dataset_bindings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  dataset_id uuid NOT NULL REFERENCES public.training_datasets(id) ON DELETE CASCADE,
  purpose text NOT NULL CHECK (purpose IN (
    'reference',
    'benchmark',
    'runtime_retrieval',
    'rag',
    'evaluation',
    'testing',
    'fine_tuning',
    'training',
    'synthetic',
    'agent_benchmarking'
  )),
  target_type text NOT NULL CHECK (target_type IN (
    'agent',
    'model',
    'department',
    'evaluation',
    'play',
    'workflow'
  )),
  target_id text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, dataset_id, purpose, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_training_dataset_bindings_org_dataset
  ON public.training_dataset_bindings (org_id, dataset_id);

CREATE INDEX IF NOT EXISTS idx_training_dataset_bindings_target
  ON public.training_dataset_bindings (org_id, target_type, target_id);

ALTER TABLE public.training_dataset_bindings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "training_dataset_bindings_org_scope"
  ON public.training_dataset_bindings;

CREATE POLICY "training_dataset_bindings_org_scope"
  ON public.training_dataset_bindings FOR ALL
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

COMMENT ON TABLE public.training_dataset_bindings IS
  'Purpose/target bindings for existing training datasets; external provider sources remain a separate future provider-neutral layer.';
