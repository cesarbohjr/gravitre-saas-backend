-- v3: Knowledge Intelligence — query clusters, glossary, knowledge gaps

CREATE TABLE IF NOT EXISTS public.org_query_clusters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  cluster_label text NOT NULL,
  member_query_count integer NOT NULL,
  failed_search_count integer NOT NULL DEFAULT 0,
  representative_queries jsonb NOT NULL DEFAULT '[]'::jsonb,
  model_id uuid REFERENCES public.trained_models(id) ON DELETE SET NULL,
  computed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.org_glossary_terms (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  term text NOT NULL,
  term_type text NOT NULL CHECK (term_type IN ('acronym', 'named_entity', 'repeated_phrase')),
  frequency integer NOT NULL DEFAULT 1,
  example_context text,
  associated_department text,
  source text NOT NULL CHECK (source IN ('query', 'document')),
  status text NOT NULL DEFAULT 'candidate'
    CHECK (status IN ('candidate', 'confirmed', 'rejected')),
  last_extracted_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, term)
);

CREATE TABLE IF NOT EXISTS public.org_knowledge_gaps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  cluster_id uuid REFERENCES public.org_query_clusters(id) ON DELETE CASCADE,
  description text NOT NULL,
  suggested_content text,
  failed_query_count integer NOT NULL,
  status text NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'resolved', 'dismissed')),
  identified_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_org_query_clusters_org
  ON public.org_query_clusters (org_id, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_org_glossary_terms_org
  ON public.org_glossary_terms (org_id, frequency DESC);

CREATE INDEX IF NOT EXISTS idx_org_knowledge_gaps_org
  ON public.org_knowledge_gaps (org_id, status, identified_at DESC);

ALTER TABLE public.org_query_clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.org_glossary_terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.org_knowledge_gaps ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_query_clusters_isolation ON public.org_query_clusters;
CREATE POLICY org_query_clusters_isolation
  ON public.org_query_clusters FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS org_glossary_terms_isolation ON public.org_glossary_terms;
CREATE POLICY org_glossary_terms_isolation
  ON public.org_glossary_terms FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS org_knowledge_gaps_isolation ON public.org_knowledge_gaps;
CREATE POLICY org_knowledge_gaps_isolation
  ON public.org_knowledge_gaps FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );
