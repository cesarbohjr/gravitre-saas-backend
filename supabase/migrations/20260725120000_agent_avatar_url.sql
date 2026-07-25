-- Agent custom avatar image (data URL or storage URL), alternative to icon+color.

DO $$
BEGIN
  IF to_regclass('public.agents') IS NOT NULL THEN
    ALTER TABLE public.agents
      ADD COLUMN IF NOT EXISTS avatar_url text;
  END IF;
END;
$$;

DO $$
BEGIN
  IF to_regclass('public.operators') IS NOT NULL THEN
    ALTER TABLE public.operators
      ADD COLUMN IF NOT EXISTS avatar_url text;
  END IF;
END;
$$;
