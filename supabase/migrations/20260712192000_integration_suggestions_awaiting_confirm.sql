-- STA-317: chat-approval parity for mutating integration-suggestion apply.
-- Mutating applies (automate_workflow, install_department_pack) stage awaiting_confirm
-- before durable writes; connect_connector remains immediate redirect.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'integration_suggestions_status_check'
      AND conrelid = 'public.integration_suggestions'::regclass
  ) THEN
    ALTER TABLE public.integration_suggestions
      DROP CONSTRAINT integration_suggestions_status_check;
  END IF;
END;
$$;

ALTER TABLE public.integration_suggestions
  ADD CONSTRAINT integration_suggestions_status_check
  CHECK (status IN ('open', 'dismissed', 'applied', 'awaiting_confirm'));

COMMENT ON COLUMN public.integration_suggestions.status IS
  'open | awaiting_confirm (mutating apply staged) | applied | dismissed';
