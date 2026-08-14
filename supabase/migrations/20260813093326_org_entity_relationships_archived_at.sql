-- Soft-archive for Learning → Relationships (operator hide without hard delete).
ALTER TABLE public.org_entity_relationships
  ADD COLUMN IF NOT EXISTS archived_at timestamptz NULL;

CREATE INDEX IF NOT EXISTS idx_org_entity_relationships_org_active
  ON public.org_entity_relationships (org_id, last_observed_at DESC)
  WHERE archived_at IS NULL;

COMMENT ON COLUMN public.org_entity_relationships.archived_at IS
  'When set, the edge is hidden from Learning Relationships UI; rebuild may recreate.';
