-- Training audit UUIDs are authenticated actor IDs. They are not guaranteed
-- to have a mirrored row in the legacy public.users profile table.
-- Preserve the actor UUID for audit without making feature writes depend on
-- an unrelated profile-sync side effect.
ALTER TABLE IF EXISTS public.training_datasets
  DROP CONSTRAINT IF EXISTS training_datasets_created_by_fkey;
ALTER TABLE IF EXISTS public.training_records
  DROP CONSTRAINT IF EXISTS training_records_created_by_fkey;
ALTER TABLE IF EXISTS public.training_jobs
  DROP CONSTRAINT IF EXISTS training_jobs_created_by_fkey;
ALTER TABLE IF EXISTS public.custom_instructions
  DROP CONSTRAINT IF EXISTS custom_instructions_created_by_fkey;

COMMENT ON COLUMN public.training_datasets.created_by IS 'Authenticated actor UUID; audit identity, not a public.users profile FK.';
COMMENT ON COLUMN public.training_records.created_by IS 'Authenticated actor UUID; audit identity, not a public.users profile FK.';
COMMENT ON COLUMN public.training_jobs.created_by IS 'Authenticated actor UUID; audit identity, not a public.users profile FK.';
COMMENT ON COLUMN public.custom_instructions.created_by IS 'Authenticated actor UUID; audit identity, not a public.users profile FK.';
