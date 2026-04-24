-- Phase 14: Expand connector types for enterprise integrations

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
    'excel',
    'custom'
  ));
