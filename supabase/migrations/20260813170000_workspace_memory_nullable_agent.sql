-- Part 1 item 1: workspace-scoped memories (org-wide; agent_id nullable).

ALTER TABLE public.agent_memories
  ALTER COLUMN agent_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_memories_org_category_created
  ON public.agent_memories (org_id, category, created_at DESC);

COMMENT ON COLUMN public.agent_memories.agent_id IS
  'Nullable agent scope; NULL means workspace/org-scoped memory shared across conversations in the org.';
