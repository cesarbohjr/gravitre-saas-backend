-- Additive: allow connector types present in app allowlist/UI but missing from
-- connectors_type_check (preflight 2026-07-16 vs ALLOWED_CONNECTOR_VENDORS).
-- Adds: ahrefs, ai_visibility_ui, clay, finseo, greenhouse.
-- Does NOT drop any prior CHECK values (pipedrive-drop lesson).
--
-- Three-part confirmation (allowlist + registration + executors), 2026-07-16:
--   greenhouse     — ALLOWED_CONNECTOR_VENDORS + hr-talent-intelligence-sources
--                    template + GREENHOUSE_TOOL_EXECUTORS (the original gap)
--   ahrefs         — allowlist + ai-search-intelligence-sources + AHREFS_TOOL_EXECUTORS
--   finseo         — allowlist + ai-search-intelligence-sources + FINSEO_TOOL_EXECUTORS
--   ai_visibility_ui — allowlist + ai-search-intelligence-sources
--                    + AI_VISIBILITY_UI_TOOL_EXECUTORS (pack #8 S2 path)
--   clay           — allowlist + CLAY_TOOL_EXECUTORS + shipped Connectors UI
--                    (apps/web/lib/connectors.ts shipped:true + connect form).
--                    No pack category template by design — BYO via Connectors,
--                    not auto-staged into Sales/Prospecting templates.
-- None are speculative/future-only names from a raw grep.

ALTER TABLE public.connectors DROP CONSTRAINT IF EXISTS connectors_type_check;

ALTER TABLE public.connectors
  ADD CONSTRAINT connectors_type_check
  CHECK (type IN (
    'absorb_lms',
    'acme_tools',
    'adp',
    'ahrefs',
    'ai_visibility_ui',
    'airtable',
    'apollo',
    'asana',
    'aws_s3',
    'bamboohr',
    'canva',
    'cisa_kev',
    'claude',
    'clay',
    'clickup',
    'clio',
    'confluence',
    'constant_contact',
    'crunchbase',
    'custom',
    'email',
    'excel',
    'fhir',
    'figma',
    'finseo',
    'fred',
    'freshdesk',
    'github',
    'gmail',
    'google_analytics',
    'google_calendar',
    'google_docs',
    'google_drive',
    'google_search_console',
    'google_sheets',
    'gorgias',
    'greenhouse',
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
