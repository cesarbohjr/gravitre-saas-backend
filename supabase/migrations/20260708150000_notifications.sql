-- STA-273: Customer-visible notifications storage (API already exists).

CREATE TABLE IF NOT EXISTS public.notifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  type text NOT NULL DEFAULT 'system',
  title text NOT NULL,
  body text NOT NULL DEFAULT '',
  entity_type text,
  entity_id uuid,
  url text,
  is_read boolean NOT NULL DEFAULT false,
  is_archived boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.notifications
  ADD COLUMN IF NOT EXISTS is_archived boolean NOT NULL DEFAULT false;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'notifications_type_check'
      AND conrelid = 'public.notifications'::regclass
  ) THEN
    ALTER TABLE public.notifications
      ADD CONSTRAINT notifications_type_check
      CHECK (type IN (
        'approval_needed',
        'assignment_created',
        'run_completed',
        'run_failed',
        'mention',
        'team_invite',
        'system'
      ));
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_notifications_org_user_created
  ON public.notifications(org_id, user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_unread
  ON public.notifications(org_id, user_id)
  WHERE is_read = false AND is_archived = false;

CREATE TABLE IF NOT EXISTS public.notification_preferences (
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, user_id)
);

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_preferences ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "notifications_user_read" ON public.notifications;
CREATE POLICY "notifications_user_read"
  ON public.notifications FOR SELECT
  USING (
    public.auth_org_accessible(org_id)
    AND user_id = auth.uid()
  );

DROP POLICY IF EXISTS "notification_preferences_user" ON public.notification_preferences;
CREATE POLICY "notification_preferences_user"
  ON public.notification_preferences FOR ALL
  USING (
    public.auth_org_accessible(org_id)
    AND user_id = auth.uid()
  )
  WITH CHECK (
    public.auth_org_accessible(org_id)
    AND user_id = auth.uid()
  );
