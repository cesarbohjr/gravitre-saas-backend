-- Provider-neutral external dataset references for Model Studio / Plays.
-- Stores references and purpose/target bindings only. No provider data is copied.

CREATE TABLE IF NOT EXISTS public.external_dataset_references (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  provider text NOT NULL,
  external_dataset_id text NOT NULL,
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
  access_mode text NOT NULL DEFAULT 'reference' CHECK (access_mode IN (
    'reference',
    'sample',
    'index'
  )),
  provider_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, provider, external_dataset_id, purpose, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_external_dataset_references_org
  ON public.external_dataset_references (org_id, provider);

CREATE INDEX IF NOT EXISTS idx_external_dataset_references_target
  ON public.external_dataset_references (org_id, target_type, target_id);

ALTER TABLE public.external_dataset_references ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "external_dataset_references_org_scope"
  ON public.external_dataset_references;

CREATE POLICY "external_dataset_references_org_scope"
  ON public.external_dataset_references FOR ALL
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

COMMENT ON TABLE public.external_dataset_references IS
  'Provider-neutral metadata references and purpose/target bindings for external datasets. No external dataset contents are materialized here.';
