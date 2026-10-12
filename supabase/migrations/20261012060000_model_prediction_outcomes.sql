-- Phase 6: predictions that can be checked against what actually happened.
--
-- A prediction logged with a subject (an account, a deal) and a horizon starts
-- as 'pending'. The labeling job resolves it from the outcome ledger or the
-- source of record ('resolved'), or marks it 'expired' when the horizon passes
-- with no evidence either way. Expired predictions are never counted as
-- negatives. Rows logged before this migration stay 'unlabeled'.
--
-- Additive and idempotent: nullable columns, one defaulted status column.
-- Preflight (read only):
--   SELECT count(*) FROM public.model_predictions;
-- Rollback:
--   ALTER TABLE public.model_predictions
--     DROP COLUMN IF EXISTS subject_type, DROP COLUMN IF EXISTS subject_id,
--     DROP COLUMN IF EXISTS horizon_days, DROP COLUMN IF EXISTS predicted_label,
--     DROP COLUMN IF EXISTS predicted_score, DROP COLUMN IF EXISTS label_status,
--     DROP COLUMN IF EXISTS outcome_label, DROP COLUMN IF EXISTS outcome_value,
--     DROP COLUMN IF EXISTS outcome_source, DROP COLUMN IF EXISTS outcome_observed_at,
--     DROP COLUMN IF EXISTS labeled_at;

ALTER TABLE public.model_predictions
  ADD COLUMN IF NOT EXISTS subject_type text,
  ADD COLUMN IF NOT EXISTS subject_id text,
  ADD COLUMN IF NOT EXISTS horizon_days integer,
  ADD COLUMN IF NOT EXISTS predicted_label text,
  ADD COLUMN IF NOT EXISTS predicted_score double precision,
  ADD COLUMN IF NOT EXISTS label_status text NOT NULL DEFAULT 'unlabeled',
  ADD COLUMN IF NOT EXISTS outcome_label text,
  ADD COLUMN IF NOT EXISTS outcome_value double precision,
  ADD COLUMN IF NOT EXISTS outcome_source text,
  ADD COLUMN IF NOT EXISTS outcome_observed_at timestamptz,
  ADD COLUMN IF NOT EXISTS labeled_at timestamptz;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'model_predictions_label_status_check'
      AND conrelid = 'public.model_predictions'::regclass
  ) THEN
    ALTER TABLE public.model_predictions
      ADD CONSTRAINT model_predictions_label_status_check
      CHECK (label_status IN ('unlabeled', 'pending', 'resolved', 'expired'));
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'model_predictions_subject_check'
      AND conrelid = 'public.model_predictions'::regclass
  ) THEN
    -- A prediction waiting for a label must say what it is about and for how long.
    ALTER TABLE public.model_predictions
      ADD CONSTRAINT model_predictions_subject_check
      CHECK (
        label_status = 'unlabeled'
        OR (subject_type IS NOT NULL AND subject_id IS NOT NULL AND horizon_days BETWEEN 1 AND 730)
      );
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'model_predictions_resolved_check'
      AND conrelid = 'public.model_predictions'::regclass
  ) THEN
    ALTER TABLE public.model_predictions
      ADD CONSTRAINT model_predictions_resolved_check
      CHECK (label_status <> 'resolved' OR (outcome_label IS NOT NULL AND outcome_source IS NOT NULL));
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_model_predictions_pending
  ON public.model_predictions (org_id, created_at)
  WHERE label_status = 'pending';
CREATE INDEX IF NOT EXISTS idx_model_predictions_subject
  ON public.model_predictions (org_id, model_id, subject_type, subject_id)
  WHERE subject_id IS NOT NULL;
