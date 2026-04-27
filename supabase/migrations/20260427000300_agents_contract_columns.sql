ALTER TABLE public.agents
  ADD COLUMN IF NOT EXISTS department text,
  ADD COLUMN IF NOT EXISTS personality jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS stats jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS last_action text,
  ADD COLUMN IF NOT EXISTS last_action_time timestamptz;

UPDATE public.agents
SET department = COALESCE(NULLIF(department, ''), 'Operations')
WHERE department IS NULL OR department = '';

UPDATE public.agents
SET personality = COALESCE(personality, '{}'::jsonb)
WHERE personality IS NULL;

UPDATE public.agents
SET stats = COALESCE(stats, '{}'::jsonb)
WHERE stats IS NULL;
