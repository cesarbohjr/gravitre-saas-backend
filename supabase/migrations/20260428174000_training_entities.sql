CREATE TABLE IF NOT EXISTS public.training_datasets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  type text NOT NULL CHECK (type IN ('examples', 'documents', 'feedback')),
  status text NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'ready', 'failed')),
  record_count integer NOT NULL DEFAULT 0 CHECK (record_count >= 0),
  created_by uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.training_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  dataset_id uuid NOT NULL REFERENCES public.training_datasets(id) ON DELETE CASCADE,
  input text NOT NULL,
  expected_output text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.training_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  dataset_id uuid NOT NULL REFERENCES public.training_datasets(id) ON DELETE CASCADE,
  model_base text NOT NULL,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'training', 'completed', 'failed')),
  progress integer NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  error text,
  created_by uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.custom_instructions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  name text NOT NULL,
  content text NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_by uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_training_datasets_org_created
  ON public.training_datasets (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_training_records_dataset_created
  ON public.training_records (dataset_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_training_jobs_org_created
  ON public.training_jobs (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_custom_instructions_org_updated
  ON public.custom_instructions (org_id, updated_at DESC);

CREATE OR REPLACE FUNCTION public.increment_training_dataset_record_count(
  p_dataset_id uuid,
  p_org_id uuid,
  p_increment integer
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE public.training_datasets
  SET record_count = GREATEST(0, record_count + COALESCE(p_increment, 0)),
      status = 'ready',
      updated_at = now()
  WHERE id = p_dataset_id AND org_id = p_org_id;
END;
$$;
