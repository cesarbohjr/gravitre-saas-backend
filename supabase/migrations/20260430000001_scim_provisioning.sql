-- SCIM provisioning tables for enterprise user management

CREATE TABLE IF NOT EXISTS public.scim_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT 'SCIM Token',
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES public.users(id),
    expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.scim_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    external_id TEXT,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, external_id)
);

CREATE TABLE IF NOT EXISTS public.scim_group_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES public.scim_groups(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(group_id, user_id)
);

ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS external_id TEXT,
ADD COLUMN IF NOT EXISTS provisioned_via TEXT DEFAULT 'manual',
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

CREATE INDEX IF NOT EXISTS idx_scim_tokens_org ON public.scim_tokens(org_id);
CREATE INDEX IF NOT EXISTS idx_scim_tokens_hash ON public.scim_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_scim_groups_org ON public.scim_groups(org_id);
CREATE INDEX IF NOT EXISTS idx_scim_groups_external ON public.scim_groups(org_id, external_id);
CREATE INDEX IF NOT EXISTS idx_scim_memberships_group ON public.scim_group_memberships(group_id);
CREATE INDEX IF NOT EXISTS idx_scim_memberships_user ON public.scim_group_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_users_external_id ON public.users(external_id);

ALTER TABLE public.scim_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scim_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scim_group_memberships ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS scim_tokens_service_role ON public.scim_tokens;
CREATE POLICY scim_tokens_service_role
  ON public.scim_tokens
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS scim_groups_service_role ON public.scim_groups;
CREATE POLICY scim_groups_service_role
  ON public.scim_groups
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS scim_memberships_service_role ON public.scim_group_memberships;
CREATE POLICY scim_memberships_service_role
  ON public.scim_group_memberships
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

COMMENT ON TABLE public.scim_tokens IS 'Bearer tokens for SCIM API authentication from IdPs';
COMMENT ON TABLE public.scim_groups IS 'Groups provisioned via SCIM from identity providers';
COMMENT ON TABLE public.scim_group_memberships IS 'User-to-group mappings from SCIM provisioning';
