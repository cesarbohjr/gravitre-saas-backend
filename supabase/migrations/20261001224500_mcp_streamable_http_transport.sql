-- Allow current MCP remote transport alongside legacy stdio/SSE/HTTP.
ALTER TABLE public.mcp_servers
  DROP CONSTRAINT IF EXISTS mcp_servers_transport_check;

ALTER TABLE public.mcp_servers
  ADD CONSTRAINT mcp_servers_transport_check
  CHECK (transport IN ('stdio', 'sse', 'http', 'streamable_http'));
