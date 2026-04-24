# Route Map — Canonical Gravitre

Legend:
- UI status: Implemented / Placeholder / Redirect / Missing
- Should exist: Yes / Redirect / No (remove)

| Route | Backend module | UI status | Should exist |
|---|---|---|---|
| `/operator` | operator runtime | Implemented | Yes |
| `/chat` | rag retrieve | Implemented | Yes (alias to RAG query) |
| `/agents` | operators | Implemented | Yes |
| `/agents/[id]` | operators | Implemented | Yes |
| `/workflows` | workflows defs | Implemented | Yes |
| `/workflows/[id]` | workflows detail/versioning | Implemented | Yes |
| `/workflows/[id]/schedules` | schedules | Implemented | Yes |
| `/runs` | workflow runs list | Implemented | Yes |
| `/runs/[id]` | run detail | Implemented | Yes |
| `/approvals` | approvals | Implemented | Yes |
| `/metrics` | metrics | Implemented | Yes |
| `/audit` | audit | Implemented | Yes |
| `/integrations` | integrations CRUD | Implemented | Yes |
| `/integrations/[id]` | integrations detail | Implemented | Yes |
| `/integrations/new` | integrations create | Implemented | Yes |
| `/sources` | rag sources | Redirect → `/rag/sources` | Redirect |
| `/rag/sources` | rag sources | Implemented | Yes |
| `/rag/sources/[id]` | rag source detail | Implemented | Yes |
| `/rag/sources/new` | rag source create | Implemented | Yes |
| `/rag/ingest` | rag ingest | Implemented | Yes |
| `/rag/ingest/[id]` | rag ingest detail | Implemented | Yes |
| `/rag/documents/[id]` | rag document detail | Implemented | Yes |
| `/connectors` | integrations (legacy) | Redirect → `/integrations` | Redirect/Remove |
| `/connectors/[id]` | integrations (legacy) | Redirect → `/integrations/[id]` | Redirect/Remove |
| `/connectors/new` | integrations (legacy) | Redirect → `/integrations/new` | Redirect/Remove |
| `/environments` | none | Placeholder | Yes (needs backend) |
| `/settings` | none | Placeholder | Yes (needs backend) |
