-- Phase 2E: proposed entity merges. The entity writer never merges on ambiguous
-- evidence; it records the case here for a person to accept or reject.
--
-- One open proposal per incoming provider record (org, system, resource). Accepting or
-- rejecting is a status change; the writer ignores records that already have a row.
--
-- Preflight (read-only):
--   SELECT to_regclass('public.org_entity_merge_proposals');          -- expect NULL
--   SELECT to_regclass('public.org_business_entities');               -- expect not NULL
--
-- Rollback: DROP TABLE IF EXISTS public.org_entity_merge_proposals;

CREATE TABLE IF NOT EXISTS public.org_entity_merge_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('company', 'person')),
  system text NOT NULL,
  resource_type text NOT NULL,
  resource_id text NOT NULL,
  incoming jsonb NOT NULL DEFAULT '{}'::jsonb,
  candidate_keys text[] NOT NULL DEFAULT '{}',
  reason text NOT NULL,
  status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'accepted', 'rejected')),
  decided_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  decided_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT org_entity_merge_proposals_record UNIQUE (org_id, system, resource_type, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_org_entity_merge_proposals_open
  ON public.org_entity_merge_proposals (org_id, created_at DESC) WHERE status = 'proposed';

ALTER TABLE public.org_entity_merge_proposals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_entity_merge_proposals_read ON public.org_entity_merge_proposals;
CREATE POLICY org_entity_merge_proposals_read
  ON public.org_entity_merge_proposals FOR SELECT
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

REVOKE INSERT, UPDATE, DELETE ON public.org_entity_merge_proposals FROM anon, authenticated;
GRANT SELECT ON public.org_entity_merge_proposals TO authenticated;
GRANT ALL ON public.org_entity_merge_proposals TO service_role;

-- The source purge (20261012010000) removes proposals with the vendor's other joins.
COMMENT ON TABLE public.org_entity_merge_proposals IS
  'Phase 2E: ambiguous entity joins awaiting a person. Never auto-merged.';
