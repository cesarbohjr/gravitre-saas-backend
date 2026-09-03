-- Memory hardening: temporal validity, provenance source_class, structured payload, history.

ALTER TABLE public.agent_memories
  ADD COLUMN IF NOT EXISTS memory_key text,
  ADD COLUMN IF NOT EXISTS valid_from timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS valid_until timestamptz,
  ADD COLUMN IF NOT EXISTS superseded_by uuid REFERENCES public.agent_memories(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS is_current boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS source_class text
    CHECK (source_class IS NULL OR source_class IN (
      'user_direct', 'model_inference', 'untrusted_external', 'workflow_outcome', 'probe'
    )),
  ADD COLUMN IF NOT EXISTS structured_payload jsonb;

CREATE INDEX IF NOT EXISTS idx_agent_memories_org_key_current
  ON public.agent_memories (org_id, memory_key, is_current)
  WHERE memory_key IS NOT NULL AND is_current IS TRUE;

COMMENT ON COLUMN public.agent_memories.memory_key IS
  'Stable identity for temporal facts (preference/decision/relationship/procedural).';
COMMENT ON COLUMN public.agent_memories.is_current IS
  'False when superseded; recall paths must filter is_current=true.';
COMMENT ON COLUMN public.agent_memories.source_class IS
  'Provenance class for contamination defense (user_direct highest trust).';
COMMENT ON COLUMN public.agent_memories.structured_payload IS
  'Structured extraction payload; raw transcript must not be the only store.';

CREATE TABLE IF NOT EXISTS public.agent_memory_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id uuid NOT NULL REFERENCES public.agent_memories(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  memory_key text,
  category text NOT NULL,
  content text NOT NULL,
  structured_payload jsonb,
  valid_from timestamptz NOT NULL,
  valid_until timestamptz NOT NULL,
  superseded_by uuid REFERENCES public.agent_memories(id) ON DELETE SET NULL,
  change_reason text,
  source_class text,
  confidence numeric(5, 2),
  provenance text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_history_org_key
  ON public.agent_memory_history (org_id, memory_key, valid_from DESC);

ALTER TABLE public.agent_memory_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "agent_memory_history_org" ON public.agent_memory_history;
CREATE POLICY "agent_memory_history_org"
  ON public.agent_memory_history FOR ALL
  USING (
    org_id = (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1
    )
  );
