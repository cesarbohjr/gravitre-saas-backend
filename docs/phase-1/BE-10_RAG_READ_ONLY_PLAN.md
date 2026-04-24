# BE-10 — RAG Read-Only Baseline: Implementation Plan

**Authority:** SYSTEM.md → docs/MASTER_PHASED_MODULE_PLAN.md  
**Phase:** 1 — Generate & Draft  
**Scope:** Read-only RAG; no autonomous agents, workflows, or external actions  
**Status:** Planning only — no code

---

## 1. Data Model (Supabase / Postgres)

### 1.1 Tables

| Table | Purpose |
|-------|--------|
| `rag_sources` | Registered sources (metadata only); org-scoped; approved-for-ingestion list |
| `rag_documents` | Document-level metadata; one row per ingested document |
| `rag_chunks` | Text chunks; content + optional metadata |
| `rag_embeddings` | Vector per chunk; pgvector; model version for invalidation |
| `rag_retrieval_logs` | Optional, minimal: query_id, org_id, result_count, latency_ms (no query text or PII in log body) |

All tables are **org-scoped** via `org_id`. Audit convention: `created_at`, `updated_at` (timestamptz); where relevant `created_by` (uuid → auth.users).

---

### 1.2 Schema (Names, Columns, Indexes)

**rag_sources**

| Column | Type | Constraints |
|--------|------|-------------|
| id | uuid | PK, default gen_random_uuid() |
| org_id | uuid | NOT NULL, FK → organizations(id) |
| title | text | NOT NULL |
| type | text | NOT NULL (e.g. 'manual', 'upload'; extensible) |
| metadata | jsonb | optional |
| created_at | timestamptz | NOT NULL, default now() |
| updated_at | timestamptz | NOT NULL, default now() |

- Index: `(org_id)`, `(org_id, type)` if filtered by type.

**rag_documents**

| Column | Type | Constraints |
|--------|------|-------------|
| id | uuid | PK, default gen_random_uuid() |
| org_id | uuid | NOT NULL, FK → organizations(id) |
| source_id | uuid | NOT NULL, FK → rag_sources(id) ON DELETE CASCADE |
| external_id | text | optional; id in external system |
| title | text | optional |
| metadata | jsonb | optional |
| created_at | timestamptz | NOT NULL, default now() |
| updated_at | timestamptz | NOT NULL, default now() |

- Unique: `(source_id, external_id)` when external_id is used for idempotency.
- Index: `(org_id)`, `(source_id)`.

**rag_chunks**

| Column | Type | Constraints |
|--------|------|-------------|
| id | uuid | PK, default gen_random_uuid() |
| org_id | uuid | NOT NULL (denormalized for RLS) |
| document_id | uuid | NOT NULL, FK → rag_documents(id) ON DELETE CASCADE |
| source_id | uuid | NOT NULL (denormalized for retrieval/citation) |
| content | text | NOT NULL |
| chunk_index | int | NOT NULL (order within document) |
| metadata | jsonb | optional |
| created_at | timestamptz | NOT NULL, default now() |

- Index: `(org_id)`, `(document_id)`, `(source_id)`.

**rag_embeddings**

| Column | Type | Constraints |
|--------|------|-------------|
| chunk_id | uuid | PK, FK → rag_chunks(id) ON DELETE CASCADE |
| org_id | uuid | NOT NULL (for RLS) |
| embedding | vector(n) | NOT NULL (n = model dimension, e.g. 1536) |
| model_version | text | NOT NULL (e.g. 'text-embedding-3-small-v1') |
| created_at | timestamptz | NOT NULL, default now() |

- Index: HNSW or IVFFlat on `embedding` (pgvector); plus `(org_id)`.

**rag_retrieval_logs** (optional, minimal)

| Column | Type | Constraints |
|--------|------|-------------|
| id | uuid | PK, default gen_random_uuid() |
| org_id | uuid | NOT NULL |
| query_id | text | NOT NULL (client or server-generated) |
| result_count | int | NOT NULL |
| latency_ms | int | optional |
| created_at | timestamptz | NOT NULL, default now() |

- Do **not** store query text or user identifiers in this table in Phase 1 (PII/safety).
- Index: `(org_id, created_at)` for time-bounded audit.

---

### 1.3 RLS Policy Strategy (High Level)

- **rag_sources:** SELECT/INSERT/UPDATE/DELETE only where `org_id` = user's org (via `organization_members`). Phase 1: ingestion is backend service-role only; RLS still enforced for any anon/key usage.
- **rag_documents:** Same org scoping; row-level `org_id` match to authenticated org.
- **rag_chunks:** Same; `org_id` must match.
- **rag_embeddings:** Same; join to chunk implies org.
- **rag_retrieval_logs:** INSERT by backend (service role); SELECT only for same org if ever exposed.

**Retrieval path:** Backend uses **service role** to query embeddings/chunks/documents/sources, but **filters strictly by org_id** from BE-00 auth context. No cross-org data ever returned.

---

### 1.4 Migrations

- One migration file: `YYYYMMDDHHMMSS_create_rag_tables.sql`.
- Contents: create tables above, create indexes, enable RLS, create policies.
- Requires: pgvector extension (already enabled in SA-00).

---

## 2. Ingestion Contract

### 2.1 How a Document Enters the System

- **Phase 1:** Controlled, explicit ingestion only. No autonomous crawling.
- **Entry points (choose one or both):**
  - **Option A — API:** `POST /api/rag/ingest` (internal/admin only; auth + org from BE-00; role check or allowlist).
  - **Option B — Admin CLI/script:** Server-side script that uses service role and inserts into `rag_documents` + `rag_chunks` + calls embedding service and writes `rag_embeddings`.

Ingestion is **not** public-facing in Phase 1; it is internal or admin-only.

### 2.2 Required Metadata (Minimum)

- **Source:** Must exist in `rag_sources` for the org (source_id). Title, type required.
- **Document:** source_id, optional external_id (for idempotency), optional title, optional metadata.
- **Chunks:** document_id, source_id, org_id, content, chunk_index. Optional metadata.

### 2.3 What Is Stored

- **rag_sources:** Registration record (title, type, org_id, timestamps).
- **rag_documents:** Per-document metadata; no raw file bytes (only references or external_id).
- **rag_chunks:** Extracted text only. No PII in content unless explicitly provided; document that PII in content is operator responsibility.
- **rag_embeddings:** Vector + model_version; no raw text duplicated.

### 2.4 Updates / Deletes (Phase 1 Constraints)

- **Update document:** Support soft update of metadata (title, metadata jsonb); optional re-ingest chunks (delete old chunks/embeddings for that document_id, re-insert).
- **Delete document:** DELETE from rag_documents; CASCADE removes chunks and embeddings. No soft delete required in Phase 1.
- **Delete source:** DELETE from rag_sources; CASCADE removes documents, chunks, embeddings. Irreversible; document in API or runbook.

**Idempotency:** When using external_id, upsert rag_documents on (source_id, external_id); then replace chunks for that document_id in a single transaction so one document = one consistent set of chunks.

---

## 3. Embedding Strategy (High-Level)

### 3.1 Model Placeholder (Config-Based)

- **Config/env:** e.g. `OPENAI_EMBEDDING_MODEL` (e.g. `text-embedding-3-small`), `OPENAI_EMBEDDING_DIMENSION` (e.g. 1536). Or local model URL + dimension.
- **Single model per deployment** in Phase 1; no per-request model selection.
- **Stored model_version:** Written to `rag_embeddings.model_version` so that re-embedding with a new model can be detected and old vectors invalidated or recreated.

### 3.2 Chunk Sizes (Range, Not Magic Number)

- **Min/max token or character range:** e.g. target 256–512 tokens (or equivalent character range) per chunk with overlap.
- **Overlap:** Configurable overlap (e.g. 50 tokens) to reduce boundary effects; document exact value in config.
- **No single magic number:** Document as "chunk_size_min", "chunk_size_max", "chunk_overlap" in config or constants; avoid hardcoded 500 everywhere.

### 3.3 Idempotency Rules

- **Per document:** One ingest run per document_id replaces all chunks and embeddings for that document. No append-only accumulation for the same document.
- **Per source:** Multiple documents per source; each document has unique document_id (and optional external_id).

---

## 4. Retrieval API Contract

### 4.1 Endpoint

**POST /api/rag/retrieve**

- **Auth:** Required. Org context from BE-00 (no org_id in body; derived from JWT/session).
- **Request body:**
  - `query` (string, required): User search/query text.
  - `top_k` (integer, optional): Max number of chunks to return (default e.g. 10; cap e.g. 50).
  - `source_id` (uuid, optional): Filter to one source.
  - `document_id` (uuid, optional): Filter to one document.
  - `min_score` (float, optional): Minimum similarity score threshold (if applicable).

### 4.2 Response (Success)

- **200 OK**
- Body:
  - `query_id` (string): Server-generated id for this retrieval (for logging/tracing).
  - `chunks` (array of objects):
    - `id` (chunk uuid)
    - `text` (string): chunk content
    - `source_id` (uuid)
    - `source_title` (string, from rag_sources.title)
    - `document_id` (uuid)
    - `document_title` (string, optional, from rag_documents.title)
    - `chunk_index` (int)
    - `score` (float): similarity score (e.g. cosine or distance)
  - `total` (int): number of chunks returned (≤ top_k).

### 4.3 Empty Result Behavior

- **No sources for org:** Return 200 with `chunks: []`, `total: 0`, and optional `message: "No sources configured"` or leave message empty.
- **No matching chunks:** Return 200 with `chunks: []`, `total: 0`. Never return fabricated chunks or hallucinated citations.
- **Embedding or backend error:** Return 503 with safe message; do not return partial or fake results.

### 4.4 Error Responses

- **400:** Invalid request (e.g. missing query, top_k out of range).
- **401:** Missing or invalid auth (BE-00).
- **403:** Valid auth but no org context (BE-00).
- **503:** Embedding service unavailable or vector search failure; body: e.g. `{ "detail": "Retrieval temporarily unavailable" }`.

---

## 5. Security + Correctness Rules

### 5.1 Org Scoping at Query Layer

- **Every retrieval** must restrict by `org_id` from auth context. No global search.
- **Implementation:** In retrieval service, set `org_id = request.state.org_id` (or equivalent from BE-00) and pass to all DB queries (sources, documents, chunks, embeddings). Never use raw user input for org_id.

### 5.2 Service Role Usage

- **Ingestion:** Backend may use Supabase **service role** to insert into rag_* tables, but must set `org_id` from authenticated context (e.g. admin) or from trusted input validated against org membership.
- **Retrieval:** Backend uses service role for read-only vector search; org filter is applied in application code and optionally reinforced by RLS so that even service role queries are constrained (e.g. RLS policy that restricts to a single org when a session variable is set).

### 5.3 PII Handling Guidance

- **Chunk content:** May contain PII if ingested documents contain it. Do not log chunk content or query text in retrieval_logs. Log only query_id, org_id, result_count, latency_ms.
- **Access control:** Only users in the same org (per BE-00) may trigger retrieval for that org; no cross-org retrieval.

### 5.4 Prompt Injection (Phase 1: Retrieval Only)

- **Phase 1:** No LLM generation in BE-10; only retrieval. So "prompt injection" into an LLM is out of scope.
- **Query string:** Treated as search input only. Do not concatenate query into prompts that are sent to external APIs in BE-10; if in the future a generation step is added, query and chunks must be passed in a structured way with clear boundaries (not raw concatenation).

---

## 6. Dependencies / Sequencing

### 6.1 Required from BE-00

- Auth middleware: valid JWT and user_id.
- Org context: org_id from `organization_members` (single-org-per-user). If org_id is null, retrieval returns 403 or empty depending on product decision; plan assumes org_id is required for retrieval.

### 6.2 SA/DB Migrations

- **SA-00:** pgvector already enabled. No change.
- **New migration:** `create_rag_tables.sql` as above (sources, documents, chunks, embeddings, retrieval_logs + RLS + indexes).

### 6.3 Config / Env Vars

- `OPENAI_API_KEY` (or equivalent for embedding provider).
- `OPENAI_EMBEDDING_MODEL` (or equivalent).
- `OPENAI_EMBEDDING_DIMENSION` (or equivalent) for vector column size.
- Optional: chunk size/overlap as env or constants (no magic numbers).

---

## 7. Stop Conditions

BE-10 planning or implementation must **halt and ask** if:

1. **Embedding provider/model not chosen:** e.g. OpenAI vs local vs another provider; exact model name and dimension. Document decision and proceed with one.
2. **Chunking strategy undefined:** Exact chunk size range and overlap (or "use default X–Y with overlap Z"); document and proceed.
3. **Ingestion entry point ambiguous:** API-only vs CLI-only vs both; and who may call (admin role, API key, etc.). Decide and document.
4. **Source registration flow unclear:** Who creates rows in `rag_sources` (manual SQL, admin API, etc.). Define and document.
5. **RLS vs service-role policy:** Whether retrieval uses RLS with a set session variable (e.g. `app.current_org_id`) or only application-level org filter. Decide and document for auditability.
6. **Conflicts with SYSTEM.md or MASTER_PHASED_MODULE_PLAN:** Any expansion (e.g. autonomous crawling, cross-org search) must be explicitly authorized and phased.

---

## 8. Explicit Out-of-Scope (BE-10)

- Autonomous agents or crawlers.
- Workflows or workflow execution.
- External actions (e.g. calling third-party APIs from RAG).
- Long-running schedulers for ingestion (unless explicitly required later).
- UI beyond existing FE-00 (no new UI required for BE-10; FE-10 may consume retrieval later).
- Cross-org source sharing or search.
- Storing raw file bytes in Postgres (metadata and chunk text only).
- LLM generation or answer synthesis in BE-10 (retrieval only; generation is a separate module if ever added).

---

## 9. Acceptance Criteria (Summary)

- [ ] Migrations create rag_sources, rag_documents, rag_chunks, rag_embeddings, rag_retrieval_logs with correct columns, indexes, and RLS.
- [ ] Ingestion path (API or CLI) writes sources/documents/chunks/embeddings with correct org_id; idempotency by document (or source+external_id) as defined.
- [ ] POST /api/rag/retrieve returns only chunks for the authenticated org; response includes source_id, document_id, titles, score; empty result when no data or no match, never fabricated citations.
- [ ] 401/403/503 and 400 handled as above; no 200 with hallucinated chunks.
- [ ] Retrieval logs (if implemented) do not store query text or PII.
- [ ] Config-based embedding model and chunk parameters; no unconfigured magic numbers.
