-- Welcome flow + role-aware dashboard preferences

ALTER TABLE public.user_preferences
  ADD COLUMN IF NOT EXISTS onboarding_completed_at timestamptz,
  ADD COLUMN IF NOT EXISTS onboarding_step text DEFAULT 'welcome',
  ADD COLUMN IF NOT EXISTS user_role text;

COMMENT ON COLUMN public.user_preferences.onboarding_completed_at IS
  'When the user finished the /welcome first-run flow (nullable = not finished).';

COMMENT ON COLUMN public.user_preferences.user_role IS
  'Primary department role selected during welcome (marketing, sales, ops, etc.).';
