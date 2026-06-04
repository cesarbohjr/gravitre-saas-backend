# Agent memory API (STA-49)

Per-agent vector memories replace mock data on the agent memory page and can be injected into workflow agent tasks.

## Data model

Table: `agent_memories`

| Column | Description |
|--------|-------------|
| `org_id`, `agent_id` | Tenant + agent scope |
| `content` | Memory text |
| `category` | `fact`, `preference`, `pattern`, `rule` |
| `provenance` | Source label (shown as “source” in UI) |
| `embedding` | `vector(1536)` for semantic search |
| `confidence`, `usage_count`, `editable` | UI metadata |

RPC: `agent_memory_search(org_id, agent_id, query_embedding, top_k, category?)`

## API

Prefix: `/api/agents/{agent_id}/memories`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/memories` | List (`?category=`, `?q=` text filter) |
| POST | `/memories` | Create (embeds on write) |
| GET | `/memories/{id}` | Get one |
| PATCH | `/memories/{id}` | Update (re-embeds when `content` changes) |
| DELETE | `/memories/{id}` | Delete (blocked when `editable=false`) |
| POST | `/memories/search` | Vector search (`query`, `topK`, `category`) |

## UI

`apps/web/app/agents/[id]/memory/page.tsx` loads memories via `agentsApi.listMemories` and supports add/edit/delete.

Next.js proxies: `app/api/agents/[id]/memories/**`

## Task-time retrieval

`run_agent_task` in `handoff_service.py` appends `<agent_memory_context>` when:

- `parameters.include_agent_memory` is set, or
- `agent.config.use_memory` / `agent.config.include_agent_memory` is true

Optional department RAG alongside memories when `parameters.include_department_rag` or `agent.config.include_department_rag` is true (uses STA-20 department filters).

## Related

- Department RAG: `docs/integration/DEPARTMENT_RAG.md` (STA-20)
- Tier 2 backlog: STA-49
