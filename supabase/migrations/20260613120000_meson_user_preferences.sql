-- STA-143: Meson user preference learning per org member

CREATE TABLE IF NOT EXISTS public.meson_user_preferences (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_meson_user_preferences_org_user
  ON public.meson_user_preferences (org_id, user_id);

ALTER TABLE public.meson_user_preferences ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "meson_user_preferences_org_scope" ON public.meson_user_preferences;
CREATE POLICY "meson_user_preferences_org_scope"
  ON public.meson_user_preferences FOR ALL
  USING (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
    AND user_id = auth.uid()
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
    AND user_id = auth.uid()
  );

DROP TRIGGER IF EXISTS trg_meson_user_preferences_updated_at ON public.meson_user_preferences;
CREATE TRIGGER trg_meson_user_preferences_updated_at
BEFORE UPDATE ON public.meson_user_preferences
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.meson_user_preferences IS
  'Per-user Meson build preferences learned from interpret/deploy events (STA-143).';
