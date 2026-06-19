-- Tier 6: Platform CS workspace tenant queue (assign / snooze)

CREATE TABLE IF NOT EXISTS public.platform_cs_tenant_queue (
  org_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
  assigned_to uuid,
  assigned_email text,
  assigned_at timestamptz,
  snoozed_until timestamptz,
  note text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid
);

CREATE INDEX IF NOT EXISTS idx_platform_cs_tenant_queue_snoozed
  ON public.platform_cs_tenant_queue (snoozed_until DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_platform_cs_tenant_queue_assigned
  ON public.platform_cs_tenant_queue (assigned_to, assigned_at DESC NULLS LAST);

ALTER TABLE public.platform_cs_tenant_queue ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.platform_cs_tenant_queue IS
  'Platform-operator CS queue actions per tenant — assign owner and snooze at-risk rollups (Tier 6).';
