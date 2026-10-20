-- Release 4 scaffold: optional MSP parent link (Option A). No behavior change until app flag ships.
--
-- Preflight (read-only):
--   SELECT column_name FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name = 'organizations' AND column_name = 'parent_org_id';
--
-- Rollback: ALTER TABLE public.organizations DROP COLUMN IF EXISTS parent_org_id;

ALTER TABLE public.organizations
  ADD COLUMN IF NOT EXISTS parent_org_id uuid REFERENCES public.organizations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_organizations_parent_org_id
  ON public.organizations (parent_org_id)
  WHERE parent_org_id IS NOT NULL;

COMMENT ON COLUMN public.organizations.parent_org_id IS
  'When set, this org is managed under an MSP parent (Release 4). Enforcement is application-layer until RLS ships.';
