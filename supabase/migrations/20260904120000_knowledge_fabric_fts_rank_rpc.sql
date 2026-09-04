-- Knowledge Fabric keyword arm: ts_rank ordering via RPC.
-- postgrest `.text_search()` cannot ORDER BY ts_rank, so keyword hits arrived in
-- arbitrary order and fusion treated them as an unordered set. This RPC returns
-- rows ranked by lexical relevance, enabling rank-aware hybrid fusion upstream.

CREATE OR REPLACE FUNCTION public.search_knowledge_chunks_fts(
  search_query text,
  match_count int DEFAULT 12,
  source_ids uuid[] DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  content text,
  citation text,
  jurisdiction text,
  authority_score double precision,
  freshness_score double precision,
  topics text[],
  source_id uuid,
  document_id uuid,
  metadata jsonb,
  ts_rank double precision
)
LANGUAGE sql
STABLE
AS $$
  WITH q AS (
    SELECT websearch_to_tsquery('english', search_query) AS tsq
  )
  SELECT
    c.id,
    c.content,
    c.citation,
    c.jurisdiction,
    c.authority_score,
    c.freshness_score,
    c.topics,
    c.source_id,
    c.document_id,
    c.metadata,
    ts_rank(c.content_tsv, q.tsq)::double precision AS ts_rank
  FROM public.knowledge_chunks c
  JOIN public.knowledge_sources s ON s.id = c.source_id
  CROSS JOIN q
  WHERE s.namespace = 'platform_shared'
    AND s.status = 'active'
    AND c.content_tsv IS NOT NULL
    AND c.content_tsv @@ q.tsq
    AND (source_ids IS NULL OR c.source_id = ANY (source_ids))
  ORDER BY ts_rank DESC
  LIMIT greatest(match_count, 1);
$$;

COMMENT ON FUNCTION public.search_knowledge_chunks_fts IS
  'Ranked keyword search over platform knowledge_chunks.content_tsv. '
  'search_query should be the OR-joined websearch string built by build_fts_query().';
