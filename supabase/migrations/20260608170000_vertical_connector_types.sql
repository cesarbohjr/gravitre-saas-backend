-- STA-114 / STA-112: allow vertical-pack demo connector types (Clio legal, FHIR healthcare).

ALTER TABLE public.connectors DROP CONSTRAINT IF EXISTS connectors_type_check;
ALTER TABLE public.connectors
  ADD CONSTRAINT connectors_type_check
  CHECK (type IN (
    'slack', 'email', 'webhook', 'salesforce', 'hubspot', 'postgresql',
    'microsoft_365', 'microsoft365', 'excel', 'custom', 'quickbooks', 'jira',
    'confluence', 'pagerduty', 'notion', 'google_analytics', 'gmail',
    'google_drive', 'google_docs', 'google_sheets', 'stripe', 'zendesk',
    'github', 'google_calendar', 'acme_tools', 'clio', 'fhir'
  ));
