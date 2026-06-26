-- v6: Lightweight entity relationship layer (soft references over existing entities)

CREATE TABLE IF NOT EXISTS public.org_entity_relationships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  source_entity_type text NOT NULL,
  source_entity_id text NOT NULL,
  relationship_type text NOT NULL,
  target_entity_type text NOT NULL,
  target_entity_id text NOT NULL,
  confidence double precision NOT NULL DEFAULT 0.5,
  evidence_count integer NOT NULL DEFAULT 1,
  last_observed_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_org_entity_relationships_unique
  ON public.org_entity_relationships (
    org_id,
    source_entity_type,
    source_entity_id,
    relationship_type,
    target_entity_type,
    target_entity_id
  );

CREATE INDEX IF NOT EXISTS idx_org_entity_relationships_source
  ON public.org_entity_relationships (org_id, source_entity_type, source_entity_id);

CREATE INDEX IF NOT EXISTS idx_org_entity_relationships_target
  ON public.org_entity_relationships (org_id, target_entity_type, target_entity_id);

ALTER TABLE public.org_entity_relationships ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_entity_relationships_isolation ON public.org_entity_relationships;
CREATE POLICY org_entity_relationships_isolation
  ON public.org_entity_relationships FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

COMMENT ON TABLE public.org_entity_relationships IS
  'v6 soft relationship layer over existing org entities; one-hop traversal only.';
