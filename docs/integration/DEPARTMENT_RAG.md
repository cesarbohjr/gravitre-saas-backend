# Department-scoped RAG (STA-20)

## Behavior

- `rag_sources.department_id` and optional `rag_sources.agent_id` scope knowledge to a department or agent.
- `rag_search` returns org-wide sources (`department_id IS NULL`) plus sources matching the caller's department.
- Workflow `rag_retrieve` steps and `POST /api/rag/retrieve` accept `agent_id` to resolve the agent's `agents.department` → `departments.id`.

## Admin API

`POST /api/rag/sources` body may include `department_id` and `agent_id`.

## Migration

`supabase/migrations/20260602130000_department_scoped_rag.sql`
