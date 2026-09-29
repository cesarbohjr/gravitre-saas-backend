-- Provider-neutral external source references for existing training_datasets.
-- This is not a second dataset product. It links an existing Gravitre dataset
-- to an external source and records how Gravitre may consume that source.
--
-- No provider credentials or access tokens belong in this table.

CREATE TABLE IF NOT EXISTS public.training_dataset_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  dataset_id uuid NOT NULL REFERENCES public.training_datasets(id) ON DELETE CASCADE,
  provider text NOT NULL,
  locator text NOT NULL,
  revision text,
  access_mode text NOT NULL CHECK (access_mode IN (
    'reference',
    'sample',
    'index',
    'materialize'
  )),
  status text NOT NULL DEFAULT 'configured' CHECK (status IN (
    'configured',
    'ready',
    'error',
    'disabled'
  )),
  license_name text,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, dataset_id, provider, locator, access_mode)
);

CREATE INDEX IF NOT EXISTS idx_training_dataset_sources_org_dataset
  ON public.training_dataset_sources (org_id, dataset_id);

CREATE INDEX IF NOT EXISTS idx_training_dataset_sources_provider
  ON public.training_dataset_sources (org_id, provider);

ALTER TABLE public.training_dataset_sources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "training_dataset_sources_org_scope"
  ON public.training_dataset_sources;

CREATE POLICY "training_dataset_sources_org_scope"
  ON public.training_dataset_sources FOR ALL
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

COMMENT ON TABLE public.training_dataset_sources IS
  'Provider-neutral external source references for existing training datasets; stores no credentials.';
