CREATE TABLE IF NOT EXISTS public.capability_marketplace_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  marketplace_source_id uuid NOT NULL REFERENCES public.capability_marketplace_sources(id) ON DELETE CASCADE,
  package_path text NOT NULL,
  name text NOT NULL,
  package_format text NOT NULL,
  version text,
  description text,
  license text,
  license_policy text NOT NULL,
  risk_level text NOT NULL,
  content_digest text,
  manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
  inspection jsonb NOT NULL DEFAULT '{}'::jsonb,
  files jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending_review'
    CHECK (status IN ('pending_review','approved','rejected','installed','stale')),
  discovered_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz,
  reviewed_by uuid,
  review_notes text,
  UNIQUE(marketplace_source_id, package_path, content_digest)
);

CREATE INDEX IF NOT EXISTS capability_marketplace_candidates_org_status_idx
  ON public.capability_marketplace_candidates(org_id, status, discovered_at DESC);

ALTER TABLE public.capability_marketplace_candidates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS capability_marketplace_candidates_org_member_read ON public.capability_marketplace_candidates;
CREATE POLICY capability_marketplace_candidates_org_member_read
  ON public.capability_marketplace_candidates FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members m
      WHERE m.org_id = capability_marketplace_candidates.org_id
        AND m.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.capability_marketplace_candidates IS
  'Discovered packages from private Git marketplaces. Sync only stages review candidates; it never installs or executes package code.';
