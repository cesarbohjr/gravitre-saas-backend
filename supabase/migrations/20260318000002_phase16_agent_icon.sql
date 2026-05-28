-- Phase 16: Agent icon support
-- Guard against migration order differences where contract tables are created later.

DO $$
BEGIN
  IF to_regclass('public.agents') IS NOT NULL THEN
    ALTER TABLE public.agents
      ADD COLUMN IF NOT EXISTS icon varchar(50),
      ADD COLUMN IF NOT EXISTS avatar_color varchar(50);
  END IF;
END;
$$;

DO $$
BEGIN
  IF to_regclass('public.operators') IS NOT NULL THEN
    ALTER TABLE public.operators
      ADD COLUMN IF NOT EXISTS icon varchar(50),
      ADD COLUMN IF NOT EXISTS avatar_color varchar(50);
  END IF;
END;
$$;
