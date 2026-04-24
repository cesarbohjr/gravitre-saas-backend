-- IN-00: Connector registry + secrets. Org-scoped; secrets encrypted at rest.
-- Authority: Phase 3/4 expansion plan

-- connectors: config per org; type = slack, email, webhook, etc.
CREATE TABLE public.connectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  type text NOT NULL CHECK (type IN ('slack', 'email', 'webhook')),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'error')),
  config jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX idx_connectors_org_id ON public.connectors(org_id);
CREATE INDEX idx_connectors_org_type ON public.connectors(org_id, type);

-- connector_secrets: encrypted key-value; never exposed to FE
CREATE TABLE public.connector_secrets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  connector_id uuid NOT NULL REFERENCES public.connectors(id) ON DELETE CASCADE,
  key_name text NOT NULL,
  encrypted_value text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (connector_id, key_name)
);

CREATE INDEX idx_connector_secrets_connector_id ON public.connector_secrets(connector_id);
CREATE INDEX idx_connector_secrets_org_id ON public.connector_secrets(org_id);

-- RLS
ALTER TABLE public.connectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.connector_secrets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "connectors_org"
  ON public.connectors FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "connector_secrets_org"
  ON public.connector_secrets FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));
