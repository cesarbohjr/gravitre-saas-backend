-- STA-263: Swarm trust fix — distinguish verified tool execution from advisory JSON output

ALTER TABLE public.agent_swarm_subtasks
  ADD COLUMN IF NOT EXISTS execution_verified boolean NOT NULL DEFAULT false;

ALTER TABLE public.agent_swarm_runs
  ADD COLUMN IF NOT EXISTS execution_verified boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.agent_swarm_subtasks.execution_verified IS
  'True when scoped tools were invoked successfully during subtask ExecutionCore run (STA-263).';

COMMENT ON COLUMN public.agent_swarm_runs.execution_verified IS
  'True when all completed subtasks with scoped tools were execution_verified (STA-263).';
