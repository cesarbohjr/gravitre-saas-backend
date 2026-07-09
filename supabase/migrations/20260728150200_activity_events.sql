-- Activity feed for connector writes and other events that do not create workflow runs.

CREATE TABLE IF NOT EXISTS public.activity_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  source text NOT NULL DEFAULT 'connector_write',
  event_type text NOT NULL DEFAULT 'task_completed',
  title text NOT NULL,
  body text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'completed',
  entity_type text,
  entity_id text,
  url text,
  integration text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_activity_events_org_user_created
  ON public.activity_events(org_id, user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_activity_events_source
  ON public.activity_events(org_id, user_id, source, created_at DESC);

ALTER TABLE public.activity_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "activity_events_user_read" ON public.activity_events;
CREATE POLICY "activity_events_user_read"
  ON public.activity_events FOR SELECT
  USING (
    public.auth_org_accessible(org_id)
    AND user_id = auth.uid()
  );
