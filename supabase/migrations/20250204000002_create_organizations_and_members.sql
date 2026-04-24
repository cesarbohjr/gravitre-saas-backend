-- BE-00: Organizations and organization_members (single-org-per-user, custom tables)
-- OQ-1: Single-Org-per-User (custom tables)

-- Organizations
CREATE TABLE public.organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Organization members (one row per user = single org per user)
CREATE TABLE public.organization_members (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'member',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id)
);

CREATE INDEX idx_organization_members_org_id ON public.organization_members(org_id);
CREATE INDEX idx_organization_members_user_id ON public.organization_members(user_id);

ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

-- Users see only their org
CREATE POLICY "org_members_select_own"
  ON public.organization_members
  FOR SELECT
  USING (auth.uid() = user_id);

-- Users see only organizations they belong to
CREATE POLICY "organizations_select_via_members"
  ON public.organizations
  FOR SELECT
  USING (
    id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

-- Service role (backend) bypasses RLS; no INSERT/UPDATE policies for anon.
-- Backend uses service_role key for creating orgs/members.
