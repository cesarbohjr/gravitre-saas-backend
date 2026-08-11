# Knowledge Fabric — Phase 0 findings

**Date:** 2026-08-11  
**Constraint:** Extend proven Gravitre architecture; no parallel schema-governance, embedding, or honesty stacks unless structurally required.  
**Licensing:** A–E classification mandatory before any ingest (see Phase 2).

---

## 0.1 Connector-action schema (G.2/G.4) vs `knowledge_sources`

| Question | Answer |
| -- | -- |
| Can ActionSpec / G.2 be **directly** extended? | **No — distinct object schema required.** |
| Can the **CI-lint process** be reused? | **Yes.** |

**Why (structural):**
- G.2/G.4 governs invoke tools (`vendor.resource.verb`, when/why, destructive hints, success verification) via `ActionSpec` (`backend/app/connectors/action_catalog/models.py`) and `test_action_schema_standard_lint.py`.
- Knowledge sources are assignment/corpus objects (`source_type` + license + authority + refresh), already partially modeled in `knowledge_source_types.py` / agent knowledge assignments — not tools.
- Forcing packs into `ActionSpec` would fake tool IDs and dual-source metadata.

**Reuse:** New `docs/engineering/knowledge-source-schema-standard.md` + pytest lint mirroring the action-schema CI pattern. Not new rows in `all_catalog_action_specs()`.

---

## 0.2 MiniLM embedding vs knowledge-pack chunks

| Path | Role today | Fit for pack chunks? |
| -- | -- | -- |
| Local MiniLM `all-MiniLM-L6-v2` (~384-d) | In-process **tool retrieval** only (`tool_retrieval_embedding.py`); no pgvector store | **No** |
| OpenAI `text-embedding-3-small` (1536-d) | Customer RAG `rag_embeddings` + semantic chunker (`rag/ingest.py`, `rag/embedding.py`) | **Yes — extend code path** |

**Test (2026-08-11 local):** `all-MiniLM-L6-v2` encode of a NIST CSF sample → **384 dims**; OpenAI corpus column **1536** → `mismatch=True`. Cannot write MiniLM vectors into OpenAI-sized pgvector without a second column/index. Chunk strategy already semantic ~256–512 tokens — no domain quality evidence requires a separate bi-encoder.

**Recommendation:** Reuse OpenAI embed + `chunk_document_text` for platform knowledge chunks stored in **separate** `knowledge_*` tables (not `rag_*`). Do **not** route pack docs through MiniLM tool-retrieval.

---

## 0.3 Department resource assignments

| Current `resource_type` CHECK | `workflow` \| `agent` \| `council` |
| Can add `knowledge_pack`? | **Yes — same pattern.** |

Extend: migration CHECK, `ResourceType` Literal in `departments.py`, Settings UI select, Lite gate where pack access is enforced.  
`org_department_pack_installs` remains install history — do not overload for Lite scoping.  
Agent-level assignment continues via `agent_knowledge_assignments` (`source_type=knowledge_pack`); department assignment scopes which packs a dept may use.

---

## 0.4 Module C honesty / confidence

| Question | Answer |
| -- | -- |
| New honesty system? | **No — extend existing.** |

Extend `retrieval_provenance.build_provenance_envelope` with `authority_score` (+ estimate/source labels via `confidence_honesty.label_confidence` pattern), fold into `AITrustLayer` sources/freshness, reuse `ConfidenceBadge` / decision transparency UI. Keep `lint-confidence-honesty.py` as the gate.

---

## Architecture decision (Phase 1+)

1. **Platform tables** `knowledge_sources` / `knowledge_documents` / `knowledge_chunks` — no customer `org_id` on shared packs; structurally separate from `rag_*`.
2. **Embeddings:** OpenAI 1536 via existing embed client; vectors on `knowledge_chunks.embedding`.
3. **Governance:** knowledge-source schema standard + CI lint (license A–E required).
4. **Sales/Marketing packs:** **HOLD** — no government API equivalent; requires Cesar’s named choice (licensed commercial **C** vs originally-authored Gravitre content). Do not ingest blog content as free-to-store.
