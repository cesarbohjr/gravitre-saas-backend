-- Align connectors constraints with backend OAuth + integration vendors (fixes OAuth start 500s).

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
    'healthy',
    'active',
    'inactive',
    'pending',
    'expired'
  ));

ALTER TABLE public.connectors
  DROP CONSTRAINT IF EXISTS connectors_type_check;

ALTER TABLE public.connectors
  ADD CONSTRAINT connectors_type_check
  CHECK (type IN (
    'slack',
    'email',
    'webhook',
    'salesforce',
    'hubspot',
    'postgresql',
    'microsoft_365',
    'microsoft365',
    'excel',
    'custom',
    'quickbooks',
    'jira',
    'confluence',
    'pagerduty',
    'notion',
    'google_analytics',
    'gmail',
    'google_drive',
    'google_docs',
    'google_sheets',
    'stripe',
    'zendesk',
    'github',
    'google_calendar'
  ));
