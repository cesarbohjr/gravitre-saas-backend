-- Allow council and decision nodes in the visual workflow builder graph tables.
ALTER TABLE public.workflow_nodes
  DROP CONSTRAINT IF EXISTS workflow_nodes_node_type_check;

ALTER TABLE public.workflow_nodes
  ADD CONSTRAINT workflow_nodes_node_type_check
  CHECK (node_type IN (
    'agent',
    'task',
    'connector',
    'tool',
    'source',
    'approval',
    'council',
    'decision'
  ));

-- Align workflow_nodes with builder persistence fields used by the API layer.
ALTER TABLE public.workflow_nodes
  ADD COLUMN IF NOT EXISTS system_icon text,
  ADD COLUMN IF NOT EXISTS system_name text,
  ADD COLUMN IF NOT EXISTS has_approval_gate boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS inputs jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS outputs jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS guardrails jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'needs_config';
