-- Phase 1: needs_connection stubs + intelligence-source connector types.
-- Template install may stage connectors before OAuth/API-key without auto-auth.

ALTER TABLE public.connectors
  DROP CONSTRAINT IF EXISTS connectors_status_check;

ALTER TABLE public.connectors
  ADD CONSTRAINT connectors_status_check
  CHECK (status IN (
    'connected',
    'disconnected',
    'error',
    'syncing',
    'pending_auth',
    'needs_connection',
    'healthy',
    'active',
    'inactive',
    'pending',
    'expired'
  ));

ALTER TABLE public.connectors DROP CONSTRAINT IF EXISTS connectors_type_check;

ALTER TABLE public.connectors
  ADD CONSTRAINT connectors_type_check
  CHECK (type IN (
    'absorb_lms',
    'acme_tools',
    'adp',
    'airtable',
    'apollo',
    'asana',
    'aws_s3',
    'bamboohr',
    'canva',
    'cisa_kev',
    'claude',
    'clickup',
    'clio',
    'confluence',
    'constant_contact',
    'crunchbase',
    'custom',
    'email',
    'excel',
    'figma',
    'fhir',
    'fred',
    'freshdesk',
    'github',
    'gmail',
    'google_analytics',
    'google_calendar',
    'google_docs',
    'google_drive',
    'google_sheets',
    'gorgias',
    'gusto',
    'hootsuite',
    'hubspot',
    'intercom',
    'jira',
    'linkedin',
    'linkedin_sales_navigator',
    'mailchimp',
    'marketo',
    'microsoft365',
    'microsoft_365',
    'microsoft_teams',
    'mixpanel',
    'monday',
    'mongodb',
    'motion',
    'n8n',
    'netsuite',
    'notion',
    'nvd',
    'odoo',
    'oecd',
    'opencorporates',
    'outlook',
    'pagerduty',
    'pdl',
    'pipedrive',
    'plaid',
    'postgresql',
    'quickbooks',
    'salesforce',
    'sec_edgar',
    'segment',
    'semrush',
    'sendgrid',
    'slack',
    'snowflake',
    'stackadapt',
    'stripe',
    'twilio',
    'webhook',
    'workday',
    'world_bank',
    'xero',
    'zapier',
    'zendesk',
    'zoominfo'
  ));

COMMENT ON CONSTRAINT connectors_status_check ON public.connectors IS
  'Includes needs_connection for marketplace template stub staging (Phase 1).';
