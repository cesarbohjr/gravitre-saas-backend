-- Phase D: temporal knowledge aliases + cognitive_turn_traces confidence join.
-- Aliases map proposal names (valid_from / valid_until / superseded_by) onto
-- existing Knowledge Fabric columns without inventing a second bi-temporal graph.

-- ---------------------------------------------------------------------------
-- knowledge_documents — proposal-aligned temporal aliases (generated columns)
-- ---------------------------------------------------------------------------
ALTER TABLE public.knowledge_documents
  ADD COLUMN IF NOT EXISTS valid_from timestamptz
    GENERATED ALWAYS AS (effective_at) STORED;

ALTER TABLE public.knowledge_documents
  ADD COLUMN IF NOT EXISTS valid_until timestamptz
    GENERATED ALWAYS AS (superseded_at) STORED;

-- superseded_by: optional FK-style pointer (nullable uuid). Not a full lineage graph.
ALTER TABLE public.knowledge_documents
  ADD COLUMN IF NOT EXISTS superseded_by uuid
    REFERENCES public.knowledge_documents(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_valid_from
  ON public.knowledge_documents (valid_from)
  WHERE valid_from IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_valid_until
  ON public.knowledge_documents (valid_until)
  WHERE valid_until IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_superseded_by
  ON public.knowledge_documents (superseded_by)
  WHERE superseded_by IS NOT NULL;

-- ---------------------------------------------------------------------------
-- cognitive_turn_traces — confidence summary for admin console join
-- ---------------------------------------------------------------------------
ALTER TABLE public.cognitive_turn_traces
  ADD COLUMN IF NOT EXISTS confidence_summary jsonb;

COMMENT ON COLUMN public.cognitive_turn_traces.confidence_summary IS
  'Module C confidence envelope for the turn (score, source, is_estimate).';
