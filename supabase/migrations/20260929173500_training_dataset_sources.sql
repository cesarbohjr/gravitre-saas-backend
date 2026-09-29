-- Provider-neutral external dataset source references for existing training datasets.
-- No provider credentials or dataset bytes are stored here.
-- Materialization remains explicit and separate; REFERENCE/INDEX/SAMPLE are preferred.

CREATE TABLE IF NOT EXISTS public.training_dataset_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  dataset_id uuid NOT NULL REFERENCES public.training_datasets(id) ON DELETE CASCADE,
  provider text NOT NULL,
  external_id text NOT NULL,
  display_name text,
  source_uri text,
  connection_ref text,
  access_mode text NOT NULL CHECK (access_mode IN (
    'reference',
    'index',
    'sample',
    'materialized'
  )),
  materialization_status text NOT NULL DEFAULT 'not_requested' CHECK (
    materialization_status IN (
      'not_requested',
      'pending',
      'materialized',
      'failed'
    )
  ),
  sample_limit integer CHECK (sample_limit IS NULL OR sample_limit > 0),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, dataset_id, provider, external_id)
);

CREATE INDEX IF NOT EXISTS idx_training_dataset_sources_org_dataset
  ON public.training_dataset_sources (org_id, dataset_id);

CREATE INDEX IF NOT EXISTS idx_training_dataset_sources_provider
  ON public.training_dataset_sources (org_id, provider, external_id);

ALTER TABLE public.training_dataset_sources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "training_dataset_sources_org_scope"
  ON public.training_dataset_sources;

CREATE POLICY "training_dataset_sources_org_scope"
  ON public.training_dataset_sources FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.training_dataset_sources IS
  'Provider-neutral external dataset references attached to existing training_datasets. No provider credentials or automatic bulk downloads.';
