CREATE TABLE IF NOT EXISTS public.capability_usage_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  package_id uuid NOT NULL REFERENCES public.capability_packages(id) ON DELETE CASCADE,
  event_type text NOT NULL CHECK (event_type IN ('selected_for_reasoning','mcp_tool_executed')),
  user_id text,
  conversation_id text,
  surface text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS capability_usage_events_org_created_idx
  ON public.capability_usage_events(org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS capability_usage_events_package_created_idx
  ON public.capability_usage_events(package_id, created_at DESC);

ALTER TABLE public.capability_usage_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS capability_usage_events_org_member_read ON public.capability_usage_events;
CREATE POLICY capability_usage_events_org_member_read
  ON public.capability_usage_events FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members m
      WHERE m.org_id = capability_usage_events.org_id
        AND m.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.capability_usage_events IS
  'Privacy-minimized portable capability usage telemetry. No prompt or skill content is stored.';
