CREATE TABLE IF NOT EXISTS public.capability_package_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  package_id uuid NOT NULL REFERENCES public.capability_packages(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  content_digest text,
  package_version text,
  snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
  resources jsonb NOT NULL DEFAULT '[]'::jsonb,
  recorded_by uuid,
  recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS capability_package_versions_digest_key
  ON public.capability_package_versions(package_id, content_digest)
  WHERE content_digest IS NOT NULL;

CREATE INDEX IF NOT EXISTS capability_package_versions_package_idx
  ON public.capability_package_versions(package_id, recorded_at DESC);

ALTER TABLE public.capability_package_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS capability_package_versions_org_member_read
  ON public.capability_package_versions;
CREATE POLICY capability_package_versions_org_member_read
  ON public.capability_package_versions FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members m
      WHERE m.org_id = capability_package_versions.org_id
        AND m.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.capability_package_versions IS
  'Immutable snapshots of installed portable capability package state and inert resources for review, update evidence, and rollback.';
