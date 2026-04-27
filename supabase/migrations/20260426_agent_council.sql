-- Agent council schema (idempotent, non-destructive)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.council_sessions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_run_id uuid REFERENCES public.runs(id) ON DELETE SET NULL,
  objective text NOT NULL,
  participating_agents jsonb NOT NULL DEFAULT '[]'::jsonb,
  debate_mode text NOT NULL DEFAULT 'consensus',
  status text NOT NULL DEFAULT 'pending',
  final_decision jsonb,
  dissenting_opinions jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.council_sessions
  ADD COLUMN IF NOT EXISTS workflow_run_id uuid REFERENCES public.runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS objective text,
  ADD COLUMN IF NOT EXISTS participating_agents jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS debate_mode text NOT NULL DEFAULT 'consensus',
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS final_decision jsonb,
  ADD COLUMN IF NOT EXISTS dissenting_opinions jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'council_sessions_debate_mode_check'
      AND conrelid = 'public.council_sessions'::regclass
  ) THEN
    ALTER TABLE public.council_sessions
      ADD CONSTRAINT council_sessions_debate_mode_check
      CHECK (debate_mode IN ('consensus', 'majority_vote', 'lead_decides'));
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'council_sessions_status_check'
      AND conrelid = 'public.council_sessions'::regclass
  ) THEN
    ALTER TABLE public.council_sessions
      ADD CONSTRAINT council_sessions_status_check
      CHECK (status IN ('pending', 'in_progress', 'resolved', 'cancelled'));
  END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.council_contributions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  session_id uuid REFERENCES public.council_sessions(id) ON DELETE CASCADE,
  agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  position text,
  confidence numeric,
  reasoning text,
  evidence_used jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.council_contributions
  ADD COLUMN IF NOT EXISTS session_id uuid REFERENCES public.council_sessions(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS position text,
  ADD COLUMN IF NOT EXISTS confidence numeric,
  ADD COLUMN IF NOT EXISTS reasoning text,
  ADD COLUMN IF NOT EXISTS evidence_used jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_council_sessions_org_id ON public.council_sessions(org_id);
CREATE INDEX IF NOT EXISTS idx_council_sessions_status ON public.council_sessions(status);
CREATE INDEX IF NOT EXISTS idx_council_sessions_created_at ON public.council_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_council_sessions_run_id ON public.council_sessions(workflow_run_id);
CREATE INDEX IF NOT EXISTS idx_council_contrib_org_id ON public.council_contributions(org_id);
CREATE INDEX IF NOT EXISTS idx_council_contrib_session_id ON public.council_contributions(session_id);
CREATE INDEX IF NOT EXISTS idx_council_contrib_agent_id ON public.council_contributions(agent_id);
CREATE INDEX IF NOT EXISTS idx_council_contrib_created_at ON public.council_contributions(created_at DESC);

ALTER TABLE public.council_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.council_contributions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "council_sessions_org_scope" ON public.council_sessions;
CREATE POLICY "council_sessions_org_scope"
  ON public.council_sessions FOR ALL
  USING (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "council_contributions_org_scope" ON public.council_contributions;
CREATE POLICY "council_contributions_org_scope"
  ON public.council_contributions FOR ALL
  USING (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  );

DROP TRIGGER IF EXISTS trg_council_sessions_updated_at ON public.council_sessions;
CREATE TRIGGER trg_council_sessions_updated_at
BEFORE UPDATE ON public.council_sessions
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
