-- Sync Now / knowledge sync create_source inserts created_by; column was never migrated.
-- Without it, HubSpot/Notion/etc Sync Now returns INTERNAL_ERROR (PGRST204).

ALTER TABLE public.rag_sources
  ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_rag_sources_created_by
  ON public.rag_sources(created_by)
  WHERE created_by IS NOT NULL;
