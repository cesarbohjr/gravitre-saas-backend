-- ML upgrade wave: retrieval ranker examples mirror for admin metrics and training sync.

CREATE TABLE IF NOT EXISTS public.retrieval_ranker_examples (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  chunk_id uuid,
  message_id uuid,
  query_text text,
  relevance_label integer NOT NULL DEFAULT 0 CHECK (relevance_label IN (0, 1)),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_ranker_examples_org_created
  ON public.retrieval_ranker_examples (org_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_retrieval_ranker_examples_dedup
  ON public.retrieval_ranker_examples (org_id, chunk_id, message_id)
  WHERE chunk_id IS NOT NULL AND message_id IS NOT NULL;

ALTER TABLE public.retrieval_ranker_examples ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS retrieval_ranker_examples_isolation ON public.retrieval_ranker_examples;
CREATE POLICY retrieval_ranker_examples_isolation
  ON public.retrieval_ranker_examples FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );
