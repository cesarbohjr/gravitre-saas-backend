-- ML model registry tables

CREATE TABLE IF NOT EXISTS public.trained_models (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  model_type text NOT NULL CHECK (model_type IN ('classifier', 'fine_tuned_llm', 'anomaly_detector', 'forecaster', 'embedding')),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'training', 'validating', 'ready', 'deployed', 'failed', 'archived')),
  current_version integer NOT NULL DEFAULT 0,
  deployed_version integer,
  dataset_id uuid REFERENCES public.training_datasets(id) ON DELETE SET NULL,
  base_model text,
  task_type text,
  target_column text,
  feature_columns jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_by uuid REFERENCES public.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.model_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id uuid NOT NULL REFERENCES public.trained_models(id) ON DELETE CASCADE,
  version integer NOT NULL,
  artifact_url text,
  artifact_size_bytes bigint,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  hyperparameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  feature_names jsonb NOT NULL DEFAULT '[]'::jsonb,
  label_encoder jsonb,
  created_by uuid REFERENCES public.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(model_id, version)
);

CREATE TABLE IF NOT EXISTS public.model_predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  model_id uuid NOT NULL REFERENCES public.trained_models(id) ON DELETE CASCADE,
  version integer NOT NULL,
  input_hash text NOT NULL,
  prediction jsonb NOT NULL,
  latency_ms integer,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trained_models_org ON public.trained_models(org_id);
CREATE INDEX IF NOT EXISTS idx_trained_models_type ON public.trained_models(org_id, model_type);
CREATE INDEX IF NOT EXISTS idx_trained_models_status ON public.trained_models(status);
CREATE INDEX IF NOT EXISTS idx_model_versions_model ON public.model_versions(model_id);
CREATE INDEX IF NOT EXISTS idx_model_predictions_model ON public.model_predictions(model_id, created_at DESC);

ALTER TABLE public.trained_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_predictions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS trained_models_org_policy ON public.trained_models;
CREATE POLICY trained_models_org_policy ON public.trained_models
  FOR ALL
  USING (
    org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid() AND om.role = 'admin'
    )
  );

DROP POLICY IF EXISTS model_versions_org_policy ON public.model_versions;
CREATE POLICY model_versions_org_policy ON public.model_versions
  FOR ALL
  USING (
    model_id IN (
      SELECT tm.id
      FROM public.trained_models tm
      JOIN public.organization_members om ON om.org_id = tm.org_id
      WHERE om.user_id = auth.uid()
    )
  )
  WITH CHECK (
    model_id IN (
      SELECT tm.id
      FROM public.trained_models tm
      JOIN public.organization_members om ON om.org_id = tm.org_id
      WHERE om.user_id = auth.uid() AND om.role = 'admin'
    )
  );

DROP POLICY IF EXISTS model_predictions_org_policy ON public.model_predictions;
CREATE POLICY model_predictions_org_policy ON public.model_predictions
  FOR ALL
  USING (
    org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid() AND om.role = 'admin'
    )
  );

COMMENT ON TABLE public.trained_models IS 'Registry of trained ML models';
COMMENT ON TABLE public.model_versions IS 'Versioned model artifacts and metrics';
COMMENT ON TABLE public.model_predictions IS 'Prediction logs for monitoring and drift detection';
