# BE-10 Implementation Decisions

**Authority:** BE-10_RAG_READ_ONLY_PLAN.md, MASTER_PHASED_MODULE_PLAN.md

| Decision | Value |
|----------|--------|
| Embedding provider | OpenAI |
| Embedding model | `text-embedding-3-small` |
| Embedding dimension | 1536 |
| Distance metric | Cosine (pgvector `<=>`; score = 1 - distance) |
| Vector index | HNSW with `vector_cosine_ops` |
| Ingestion entry point (Phase 1) | CLI-only (admin script under `backend/scripts/rag_ingest.py`) |

- **RLS:** Org-scoped policies on all RAG tables; backend uses service role and filters strictly by `org_id` from auth context.
- **Retrieval:** `POST /api/rag/retrieve`; org from BE-00 auth; no `org_id` in body.
