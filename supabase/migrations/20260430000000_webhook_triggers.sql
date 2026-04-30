-- Webhook triggers for workflow execution

ALTER TABLE public.workflow_defs
ADD COLUMN IF NOT EXISTS webhook_config JSONB DEFAULT '{
  "enabled": false,
  "secret": null,
  "allowed_ips": null,
  "rate_limit_per_minute": 60
}'::jsonb;

ALTER TABLE public.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_trigger_type_check;

ALTER TABLE public.workflow_runs
  ADD CONSTRAINT workflow_runs_trigger_type_check
  CHECK (trigger_type IN ('manual', 'schedule', 'rollback', 'webhook', 'api'));

CREATE INDEX IF NOT EXISTS idx_workflow_runs_trigger_type ON public.workflow_runs(trigger_type);

COMMENT ON COLUMN public.workflow_defs.webhook_config IS
  'Configuration for webhook triggers: enabled, secret, allowed_ips, rate_limit_per_minute';
