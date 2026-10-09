-- Agents > Instructions: guidance vs guardrail, and department scope.
-- Additive and backward compatible: existing rows become whole-team (or
-- single-agent) guidance. The API falls back to the old columns until this runs.
ALTER TABLE IF EXISTS public.custom_instructions
  ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'guidance',
  ADD COLUMN IF NOT EXISTS department text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'custom_instructions_kind_check'
  ) THEN
    ALTER TABLE public.custom_instructions
      ADD CONSTRAINT custom_instructions_kind_check
      CHECK (kind IN ('guidance', 'guardrail'));
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'custom_instructions_department_check'
  ) THEN
    ALTER TABLE public.custom_instructions
      ADD CONSTRAINT custom_instructions_department_check
      CHECK (
        department IS NULL
        OR department IN (
          'sales', 'marketing', 'customer_success', 'operations',
          'finance', 'engineering', 'security', 'general'
        )
      );
  END IF;
END $$;

COMMENT ON COLUMN public.custom_instructions.kind IS
  'guidance: shapes how agents work. guardrail: a hard limit agents must not cross.';
COMMENT ON COLUMN public.custom_instructions.department IS
  'Roster department id the instruction applies to. NULL with agent_id NULL means the whole team.';
