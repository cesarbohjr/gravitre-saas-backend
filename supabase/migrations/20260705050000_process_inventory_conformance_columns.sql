-- Process mining / digital twin columns for organization_process_inventory.

ALTER TABLE public.organization_process_inventory
  ADD COLUMN IF NOT EXISTS workflow_id uuid REFERENCES public.workflows(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS declared_steps jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS automation_potential_score numeric,
  ADD COLUMN IF NOT EXISTS automation_level text;

CREATE INDEX IF NOT EXISTS idx_organization_process_inventory_workflow
  ON public.organization_process_inventory (org_id, workflow_id)
  WHERE workflow_id IS NOT NULL;

COMMENT ON COLUMN public.organization_process_inventory.workflow_id IS
  'Optional linked workflow for observed-vs-declared conformance checks.';
COMMENT ON COLUMN public.organization_process_inventory.declared_steps IS
  'Admin-declared step sequence (json array of strings) for process conformance.';
COMMENT ON COLUMN public.organization_process_inventory.automation_potential_score IS
  'Advisory automation opportunity score for digital twin summaries.';
COMMENT ON COLUMN public.organization_process_inventory.automation_level IS
  'manual | partial | automated — admin-entered automation maturity.';
