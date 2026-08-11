-- Repair missing Phase 16 agent appearance columns.
-- operators already had icon/avatar_color; agents was missing them in prod
-- (PostgREST: "Could not find the 'avatar_color' column of 'agents'").

ALTER TABLE public.agents
  ADD COLUMN IF NOT EXISTS icon varchar(50),
  ADD COLUMN IF NOT EXISTS avatar_color varchar(50);
