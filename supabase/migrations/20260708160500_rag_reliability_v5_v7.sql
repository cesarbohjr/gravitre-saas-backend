-- v5: RAG chunk outcome tracking for source reliability scoring
-- v7: Unified response evaluations + message feedback

CREATE TABLE IF NOT EXISTS public.message_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  message_id uuid NOT NULL,
  feedback text NOT NULL CHECK (feedback IN ('helpful', 'not_helpful')),
  reason text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_message_feedback_message
  ON public.message_feedback (message_id);

CREATE INDEX IF NOT EXISTS idx_message_feedback_org_created
  ON public.message_feedback (org_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.rag_chunk_outcomes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  message_id uuid NOT NULL,
  chunk_id uuid REFERENCES public.rag_chunks(id) ON DELETE SET NULL,
  source_document_id uuid,
  rerank_score double precision,
  rank_position integer,
  outcome_helpful boolean,
  retrieval_latency_ms integer,
  recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rag_chunk_outcomes_message
  ON public.rag_chunk_outcomes (message_id);

CREATE INDEX IF NOT EXISTS idx_rag_chunk_outcomes_org_document
  ON public.rag_chunk_outcomes (org_id, source_document_id)
  WHERE outcome_helpful IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.response_evaluations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  message_id uuid NOT NULL,
  surface text NOT NULL,
  rag_quality_score double precision,
  user_feedback text CHECK (user_feedback IS NULL OR user_feedback IN ('helpful', 'not_helpful')),
  feedback_reason text,
  chunk_outcome_summary jsonb,
  retrieval_latency_ms integer,
  response_latency_ms integer,
  composite_score double precision,
  evaluated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_response_evaluations_message
  ON public.response_evaluations (message_id);

CREATE INDEX IF NOT EXISTS idx_response_evaluations_org_evaluated
  ON public.response_evaluations (org_id, evaluated_at DESC);

ALTER TABLE public.user_query_patterns
  ADD COLUMN IF NOT EXISTS message_id uuid;

CREATE INDEX IF NOT EXISTS idx_user_query_patterns_message
  ON public.user_query_patterns (message_id)
  WHERE message_id IS NOT NULL;

ALTER TABLE public.message_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_chunk_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.response_evaluations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS message_feedback_isolation ON public.message_feedback;
CREATE POLICY message_feedback_isolation
  ON public.message_feedback FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS rag_chunk_outcomes_isolation ON public.rag_chunk_outcomes;
CREATE POLICY rag_chunk_outcomes_isolation
  ON public.rag_chunk_outcomes FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS response_evaluations_isolation ON public.response_evaluations;
CREATE POLICY response_evaluations_isolation
  ON public.response_evaluations FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

COMMENT ON TABLE public.rag_chunk_outcomes IS
  'v5 per-chunk retrieval outcomes linked to assistant message_id; outcome_helpful set on feedback.';
COMMENT ON TABLE public.response_evaluations IS
  'v7 unified evaluation record consolidating v2/v5 quality signals per response.';
