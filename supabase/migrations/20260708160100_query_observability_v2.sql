-- v2: query observability columns (normalization, surface metadata, failed search, feedback)

ALTER TABLE public.user_query_patterns
  ADD COLUMN IF NOT EXISTS normalized_query_text text,
  ADD COLUMN IF NOT EXISTS surface text,
  ADD COLUMN IF NOT EXISTS agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS department text,
  ADD COLUMN IF NOT EXISTS is_failed_search boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS feedback_helpful boolean,
  ADD COLUMN IF NOT EXISTS rag_quality_score double precision;

CREATE INDEX IF NOT EXISTS idx_user_query_patterns_org_normalized
  ON public.user_query_patterns (org_id, normalized_query_text)
  WHERE normalized_query_text IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_query_patterns_org_failed
  ON public.user_query_patterns (org_id, is_failed_search, created_at DESC)
  WHERE is_failed_search = true;

COMMENT ON COLUMN public.user_query_patterns.normalized_query_text IS
  'Lowercased/stemmed query text for clustering and analytics (v2).';
