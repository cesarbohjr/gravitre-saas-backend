-- Align the existing registry's type constraint with app.ml.base.ModelType.
-- Production preflight confirmed the legacy constraint excludes regressor and
-- causal_model. This blocks the implemented world-model artifact registration.
-- No model statuses, rows, RLS policies, grants, consent or deployment pointers
-- are changed. Production application requires explicit owner approval.
ALTER TABLE public.trained_models
  DROP CONSTRAINT trained_models_model_type_check,
  ADD CONSTRAINT trained_models_model_type_check CHECK (
    model_type IN (
      'classifier', 'regressor', 'causal_model', 'fine_tuned_llm',
      'anomaly_detector', 'forecaster', 'embedding'
    )
  );
