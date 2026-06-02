-- STA-16: HubSpot inbound workflow trigger type

ALTER TABLE public.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_trigger_type_check;

ALTER TABLE public.workflow_runs
  ADD CONSTRAINT workflow_runs_trigger_type_check
  CHECK (trigger_type IN ('manual', 'schedule', 'rollback', 'webhook', 'api', 'hubspot'));

COMMENT ON COLUMN public.connectors.config IS
  'Connector config; hubspot_triggers: [{ event, workflow_id, property?, active }] for inbound HubSpot events';
