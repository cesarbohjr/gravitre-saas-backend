-- Persist profile job title + department on public.users so Team, Approvals,
-- and chat can resolve identity from the same source of truth as /api/auth/me.
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS job_title text,
  ADD COLUMN IF NOT EXISTS department text;

COMMENT ON COLUMN public.users.job_title IS 'User profile job title / position (self-serve via /settings/profile).';
COMMENT ON COLUMN public.users.department IS 'User profile department (self-serve via /settings/profile).';
