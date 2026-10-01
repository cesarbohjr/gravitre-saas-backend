-- Portable MCP writes must not be recorded as terminal success before
-- independent source-of-record verification exists.
ALTER TABLE public.mcp_tool_executions
  DROP CONSTRAINT IF EXISTS mcp_tool_executions_status_check;

ALTER TABLE public.mcp_tool_executions
  ADD CONSTRAINT mcp_tool_executions_status_check
  CHECK (status IN (
    'pending_approval',
    'approved',
    'rejected',
    'completed',
    'failed',
    'timeout',
    'accepted',
    'verifying',
    'verification_inconclusive'
  ));

COMMENT ON COLUMN public.mcp_tool_executions.status IS
  'MCP execution lifecycle. Portable write provider acceptance is not completed until independently verified.';
