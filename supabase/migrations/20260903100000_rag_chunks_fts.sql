-- Persisted keyword index for org-scoped RAG chunks.
--
-- The Knowledge Fabric has had this since 20260811180000; org RAG never did.
-- The consequence was not "no keyword search" -- org RAG does run BM25, and
-- unlike the Fabric's FTS arm it produces a real relevance ORDER. The
-- consequence was that BM25 had nothing to rank except an arbitrary slice:
--
--   backend/app/rag/retrieval.py, fetch_bm25_corpus()
--     client.table("rag_chunks").select(...).eq("org_id", ...).limit(500)
--
-- No query terms and no ORDER BY. Under 500 chunks per (org, environment) that
-- is the whole corpus and the arm is exact. Over 500 it silently becomes a
-- sample, chosen by whatever order Postgres felt like returning, and nothing
-- reports which of the two regimes an org is in.
--
-- Measured before writing this, per the standing lesson about reachability:
-- docs/delivery/orgrag-keyword-reach.json records 1 chunk platform-wide, so no
-- scope is over the line today. This is a latent trap, not a live defect. It
-- fires the first time a customer uploads a real corpus, and it fires silently.
--
-- Mirrors the Fabric's definition exactly (same config, same generated-column
-- form) so the two keyword arms cannot drift apart in stemming behaviour.

ALTER TABLE public.rag_chunks
  ADD COLUMN IF NOT EXISTS content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_rag_chunks_fts
  ON public.rag_chunks USING gin (content_tsv);

-- Scope columns are always applied alongside the keyword filter, so the
-- composite matters more than org_id alone for this access path.
CREATE INDEX IF NOT EXISTS idx_rag_chunks_org_env
  ON public.rag_chunks (org_id, environment);

-- Contextual chunk enrichment (Anthropic's Contextual Retrieval pattern).
--
-- Persisted rather than discarded after embedding, for two reasons. It makes the
-- enrichment auditable -- you can see what a chunk was embedded WITH, not just
-- guess. And it distinguishes "this chunk was never enriched" from "this chunk
-- was enriched and the context happened to be empty", which are different facts
-- that an unpersisted prefix would render identical.
--
-- `content` is untouched and remains the only thing ever shown or cited. The
-- prefix affects the vector, never the answer.
ALTER TABLE public.rag_chunks
  ADD COLUMN IF NOT EXISTS context_prefix text;

COMMENT ON COLUMN public.rag_chunks.context_prefix IS
  'Generated context prepended to the chunk before embedding, so a passage stays '
  'findable after chunking strips its referents. NULL means unenriched. Never '
  'displayed or cited: content is the only user-facing text.';

COMMENT ON COLUMN public.rag_chunks.content_tsv IS
  'Generated FTS vector. Lets the keyword arm select candidates in Postgres '
  'instead of ranking an arbitrary 500-row slice in memory. BM25 still does the '
  'ranking -- this only fixes which rows it gets to rank.';
