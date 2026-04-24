-- Phase 14: Allow approval node type in orchestration

ALTER TABLE public.workflow_nodes
  DROP CONSTRAINT IF EXISTS workflow_nodes_node_type_check;

ALTER TABLE public.workflow_nodes
  ADD CONSTRAINT workflow_nodes_node_type_check
  CHECK (node_type IN ('agent', 'task', 'connector', 'tool', 'source', 'approval'));
