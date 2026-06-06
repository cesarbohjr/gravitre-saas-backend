-- STA-72: Partner marketplace sandbox org provisioning

-- Allow users to belong to publisher org + isolated sandbox org.
ALTER TABLE public.organization_members
  DROP CONSTRAINT IF EXISTS organization_members_user_id_key;

CREATE TABLE IF NOT EXISTS public.marketplace_sandbox_orgs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  publisher_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  sandbox_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  created_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT marketplace_sandbox_orgs_publisher_key UNIQUE (publisher_org_id),
  CONSTRAINT marketplace_sandbox_orgs_sandbox_key UNIQUE (sandbox_org_id)
);

CREATE INDEX IF NOT EXISTS idx_marketplace_sandbox_publisher
  ON public.marketplace_sandbox_orgs(publisher_org_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_sandbox_sandbox
  ON public.marketplace_sandbox_orgs(sandbox_org_id);

ALTER TABLE public.marketplace_sandbox_orgs ENABLE ROW LEVEL SECURITY;

-- Partner sandbox connector vendor (published marketplace connectors).
ALTER TABLE public.connectors DROP CONSTRAINT IF EXISTS connectors_type_check;
ALTER TABLE public.connectors
  ADD CONSTRAINT connectors_type_check
  CHECK (type IN (
    'slack', 'email', 'webhook', 'salesforce', 'hubspot', 'postgresql',
    'microsoft_365', 'microsoft365', 'excel', 'custom', 'quickbooks', 'jira',
    'confluence', 'pagerduty', 'notion', 'google_analytics', 'gmail',
    'google_drive', 'google_docs', 'google_sheets', 'stripe', 'zendesk',
    'github', 'google_calendar', 'acme_tools'
  ));
