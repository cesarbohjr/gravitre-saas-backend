-- Optional Voyage embedding column (1024-dim) for gradual corpus re-index.
-- See docs/voyage-reindex-runbook.md

ALTER TABLE public.rag_embeddings
  ADD COLUMN IF NOT EXISTS embedding_voyage vector(1024);

CREATE INDEX IF NOT EXISTS idx_rag_embeddings_voyage_hnsw
  ON public.rag_embeddings
  USING hnsw (embedding_voyage vector_cosine_ops);
