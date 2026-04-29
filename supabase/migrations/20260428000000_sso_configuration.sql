-- SSO Configuration for Organizations (Command tier only)
CREATE TABLE IF NOT EXISTS public.sso_configurations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,

  -- Provider type
  provider_type TEXT NOT NULL CHECK (provider_type IN ('saml', 'oidc')),
  is_enabled BOOLEAN DEFAULT false,

  -- SAML Configuration
  saml_entity_id TEXT,
  saml_sso_url TEXT,
  saml_slo_url TEXT,
  saml_certificate TEXT,
  saml_name_id_format TEXT DEFAULT 'urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress',

  -- OIDC Configuration
  oidc_issuer TEXT,
  oidc_client_id TEXT,
  oidc_client_secret TEXT,
  oidc_authorization_endpoint TEXT,
  oidc_token_endpoint TEXT,
  oidc_userinfo_endpoint TEXT,
  oidc_scopes TEXT DEFAULT 'openid email profile',

  -- Attribute mapping
  attribute_mapping JSONB DEFAULT '{
    "email": "email",
    "first_name": "firstName",
    "last_name": "lastName",
    "groups": "groups"
  }'::jsonb,

  -- Settings
  auto_provision_users BOOLEAN DEFAULT true,
  default_role TEXT DEFAULT 'member',
  allowed_domains TEXT[],

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,

  UNIQUE(org_id)
);

CREATE TABLE IF NOT EXISTS public.sso_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,

  -- Request state
  state TEXT NOT NULL UNIQUE,
  nonce TEXT,
  relay_state TEXT,

  -- Response data
  idp_session_id TEXT,
  authenticated_at TIMESTAMP WITH TIME ZONE,

  -- Lifecycle
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sso_configurations_org ON public.sso_configurations(org_id);
CREATE INDEX IF NOT EXISTS idx_sso_sessions_state ON public.sso_sessions(state);
CREATE INDEX IF NOT EXISTS idx_sso_sessions_expires ON public.sso_sessions(expires_at);

ALTER TABLE public.sso_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sso_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Org admins can manage SSO config" ON public.sso_configurations;
CREATE POLICY "Org admins can manage SSO config"
  ON public.sso_configurations
  FOR ALL
  USING (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om
      WHERE om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin')
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om
      WHERE om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin')
    )
  );

DROP POLICY IF EXISTS "SSO sessions service only" ON public.sso_sessions;
CREATE POLICY "SSO sessions service only"
  ON public.sso_sessions
  FOR ALL
  USING (false)
  WITH CHECK (false);
