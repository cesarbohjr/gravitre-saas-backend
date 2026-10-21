-- Freeze actual retrieval features before feedback. Legacy observations stay
-- NULL and cannot become independent federation holdouts by reconstruction.
ALTER TABLE public.rag_chunk_outcomes
  ADD COLUMN IF NOT EXISTS ranker_features jsonb,
  ADD COLUMN IF NOT EXISTS ranker_features_observed_at timestamptz;
ALTER TABLE public.rag_chunk_outcomes
  ADD CONSTRAINT rag_chunk_outcomes_ranker_snapshot_check CHECK (
    (ranker_features IS NULL AND ranker_features_observed_at IS NULL)
    OR (ranker_features IS NOT NULL AND ranker_features_observed_at IS NOT NULL
      AND ranker_features_observed_at <= recorded_at
      AND jsonb_typeof(ranker_features) = 'object'
      AND ranker_features ?& ARRAY['rerank_score','source_reliability_score','rank_position','source_document_age_days']
      AND ranker_features - ARRAY['rerank_score','source_reliability_score','rank_position','source_document_age_days'] = '{}'::jsonb
      AND jsonb_typeof(ranker_features->'rerank_score') = 'number'
      AND jsonb_typeof(ranker_features->'source_reliability_score') = 'number'
      AND jsonb_typeof(ranker_features->'rank_position') = 'number'
      AND jsonb_typeof(ranker_features->'source_document_age_days') = 'number')
  );
CREATE INDEX IF NOT EXISTS idx_rag_chunk_outcomes_federated_holdout
  ON public.rag_chunk_outcomes (org_id, ranker_features_observed_at, recorded_at, id)
  WHERE ranker_features IS NOT NULL AND outcome_helpful IS NOT NULL;
COMMENT ON COLUMN public.rag_chunk_outcomes.ranker_features IS
  'Pre-feedback retrieval feature snapshot for consented tenant-local aggregate evaluation. No text, prompts or generated content.';
-- Existing table RLS, grants, labels, deployed pointers and consent are unchanged.
