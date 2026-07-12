-- STA-316 Memory Phase 1 Option B: opaque-token entity embeddings (separate from rag_embeddings).
-- Never store raw email/name/alias text in this table.

CREATE TABLE IF NOT EXISTS public.org_memory_entity_embeddings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  integration text NOT NULL DEFAULT '',
  entity_type text NOT NULL,
  entity_id text NOT NULL,
  -- Opaque digest kind: 'entity' (entity_id token) or 'alias' (HMAC of normalized alias)
  token_kind text NOT NULL DEFAULT 'entity'
    CHECK (token_kind IN ('entity', 'alias')),
  -- Hex digest only — never raw PII. Used for audit/debug of which opaque token was embedded.
  token_digest text NOT NULL,
  embedding vector(1536) NOT NULL,
  model_version text NOT NULL DEFAULT 'text-embedding-3-small',
  token_version text NOT NULL DEFAULT 'v1',
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '30 days')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_org_memory_entity_embeddings_unique
  ON public.org_memory_entity_embeddings (
    org_id, integration, entity_type, entity_id, token_kind, token_digest, model_version
  );

CREATE INDEX IF NOT EXISTS idx_org_memory_entity_embeddings_org_expiry
  ON public.org_memory_entity_embeddings (org_id, expires_at);

CREATE INDEX IF NOT EXISTS idx_org_memory_entity_embeddings_hnsw
  ON public.org_memory_entity_embeddings
  USING hnsw (embedding vector_cosine_ops);

ALTER TABLE public.org_memory_entity_embeddings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_memory_entity_embeddings_member_all ON public.org_memory_entity_embeddings;
CREATE POLICY org_memory_entity_embeddings_member_all
  ON public.org_memory_entity_embeddings
  FOR ALL
  USING (
    org_id IN (
      SELECT organization_members.org_id
      FROM public.organization_members
      WHERE organization_members.user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT organization_members.org_id
      FROM public.organization_members
      WHERE organization_members.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.org_memory_entity_embeddings IS
  'STA-316 Option B: Memory entity embeddings of opaque tokens only — never raw PII; not mixed into rag_embeddings.';

-- Org-scoped vector search for Memory (service role / member RLS).
CREATE OR REPLACE FUNCTION public.match_org_memory_entity_embeddings(
  p_org_id uuid,
  p_query_embedding vector(1536),
  p_integration text DEFAULT NULL,
  p_entity_type text DEFAULT NULL,
  p_match_count int DEFAULT 5,
  p_min_score float DEFAULT 0.75
)
RETURNS TABLE (
  id uuid,
  integration text,
  entity_type text,
  entity_id text,
  token_kind text,
  token_digest text,
  model_version text,
  score float
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    e.id,
    e.integration,
    e.entity_type,
    e.entity_id,
    e.token_kind,
    e.token_digest,
    e.model_version,
    (1 - (e.embedding <=> p_query_embedding))::float AS score
  FROM public.org_memory_entity_embeddings e
  WHERE e.org_id = p_org_id
    AND e.expires_at > now()
    AND (p_integration IS NULL OR e.integration = p_integration)
    AND (p_entity_type IS NULL OR e.entity_type = p_entity_type)
    AND (1 - (e.embedding <=> p_query_embedding)) >= p_min_score
  ORDER BY e.embedding <=> p_query_embedding
  LIMIT GREATEST(1, LEAST(COALESCE(p_match_count, 5), 20));
$$;

-- Hard-delete expired rows and optional full org purge.
CREATE OR REPLACE FUNCTION public.purge_org_memory_entity_embeddings(
  p_org_id uuid,
  p_expired_only boolean DEFAULT true
)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  deleted_count integer;
BEGIN
  IF p_expired_only THEN
    DELETE FROM public.org_memory_entity_embeddings
    WHERE org_id = p_org_id AND expires_at <= now();
  ELSE
    DELETE FROM public.org_memory_entity_embeddings
    WHERE org_id = p_org_id;
  END IF;
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$;
