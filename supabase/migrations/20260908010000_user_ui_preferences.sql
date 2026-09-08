-- Per-user UI preferences (dashboard layout, etc.) scoped by org + user.

CREATE TABLE IF NOT EXISTS public.user_ui_preferences (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_ui_preferences_org_user
  ON public.user_ui_preferences (org_id, user_id);

ALTER TABLE public.user_ui_preferences ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_ui_preferences_own_row" ON public.user_ui_preferences;
CREATE POLICY "user_ui_preferences_own_row"
  ON public.user_ui_preferences FOR ALL
  USING (
    user_id = auth.uid()
    AND org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    user_id = auth.uid()
    AND org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  );

DROP TRIGGER IF EXISTS trg_user_ui_preferences_updated_at ON public.user_ui_preferences;
CREATE TRIGGER trg_user_ui_preferences_updated_at
BEFORE UPDATE ON public.user_ui_preferences
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.user_ui_preferences IS
  'Per-user UI preferences including home dashboard widget layout (org-scoped).';
