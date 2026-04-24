# DC-00 — RAG Source Registration + Ingestion API

**Status:** Implemented  
**Authority:** docs/MASTER_PHASED_MODULE_PLAN.md Part V  
**Dependencies:** BE-10 tables, RB-00 admin enforcement

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/rag/sources | Auth | List sources |
| POST | /api/rag/sources | Admin | Create source |
| PATCH | /api/rag/sources/:id | Admin | Update source (title/metadata) |
| GET | /api/rag/sources/:id | Auth | Get source |
| GET | /api/rag/documents?source_id= | Auth | List documents for source |
| GET | /api/rag/documents/:id | Auth | Document metadata; chunks optional (admin only) |
| POST | /api/rag/ingest | Admin | Controlled ingestion |
| GET | /api/rag/ingest/:id | Auth | Ingest job status |

---

## Ingestion Request (Choose One)

### A) chunks[] mode
```json
{
  "source_id": "uuid",
  "external_id": "optional",
  "title": "optional",
  "metadata": {},
  "chunks": ["text...", "text..."]
}
```

### B) text mode (server chunking)
```json
{
  "source_id": "uuid",
  "external_id": "optional",
  "title": "optional",
  "metadata": {},
  "text": "raw text...",
  "chunking": { "target_tokens_min": 256, "target_tokens_max": 512, "overlap_tokens": 50 }
}
```

---

## Idempotency + Replace Semantics (Atomic Ingest)

- If `external_id` provided: create a **new inactive document version**.
- Chunks + embeddings are written to the new version.
- Only after **full success** is the new version activated and the previous version archived.
- If ingest fails, the previous active version remains intact.
- If `external_id` omitted: new document created every time.

---

## Size Limits

- Max text bytes: **2 MiB**
- Max chunks: **500**
- Max chunk bytes: **16 KiB**

---

## Chunking Defaults (text mode)

Deterministic char‑based chunking (approx 4 chars/token):
- min ≈ 256 tokens (1024 chars)
- max ≈ 512 tokens (2048 chars)
- overlap ≈ 50 tokens (200 chars)

Client‑supplied chunking values are bounded:
- min ≤ 4096 chars, max ≤ 8192 chars, overlap < max

---

## Audit Events

| Action | When | Metadata |
|--------|------|----------|
| rag.source.created | POST /sources | type |
| rag.source.updated | PATCH /sources/:id | fields |
| rag.ingest.started | POST /ingest | source_id, has_external_id |
| rag.ingest.completed | success | source_id, document_id, chunk_count, has_external_id |
| rag.ingest.failed | failure | source_id, has_external_id |

**No raw text or PII in audit metadata.**

---

## Non‑Goals

- No crawling or external fetching  
- No raw file bytes stored  
- No ingestion of URLs  
- No PII or text in logs

---

## Manual Consistency Test Plan (No Partial Writes)

1. Ingest a document with `external_id`.
2. Force a failure mid‑ingest (e.g., invalid OpenAI key).
3. Verify:
   - Previous document remains active and retrievable.
   - Failed staged version is removed.
4. Re‑ingest with valid embeddings:
   - New version becomes active.
   - Retrieval returns only the new content.
