-- Phase 16: Agent icon support

ALTER TABLE public.agents
  ADD COLUMN IF NOT EXISTS icon varchar(50),
  ADD COLUMN IF NOT EXISTS avatar_color varchar(50);

ALTER TABLE public.operators
  ADD COLUMN IF NOT EXISTS icon varchar(50),
  ADD COLUMN IF NOT EXISTS avatar_color varchar(50);
