# Knowledge Fabric — implementation (2026-08-11)

## Phase 0 (reuse)

See `docs/delivery/knowledge-fabric-phase0-findings.md`.

| Area | Decision |
| -- | -- |
| Schema governance | Distinct knowledge-source standard + CI lint (not ActionSpec) |
| Embeddings | Extend OpenAI 1536 RAG path; MiniLM 384 ≠ corpus (tested) |
| Departments | Add `knowledge_pack` to `department_resource_assignments` |
| Honesty | Extend Module C provenance + citation UI |

## Phase 1 — Schema

- Migration `20260811180000_platform_knowledge_fabric.sql` applied to prod (`db push`)
- Tables: `knowledge_sources`, `knowledge_documents`, `knowledge_chunks` (`namespace=platform_shared`)
- Separate from `rag_*`; RLS authenticated SELECT only; service-role ingest
- Standard: `docs/engineering/knowledge-source-schema-standard.md`
- Lint: `backend/tests/knowledge_fabric/test_knowledge_source_schema_lint.py`

## Phase 2 — Ingest (licensed)

| Pack | Status | License | Notes |
| -- | -- | -- | -- |
| Cybersecurity | Ingested | A (NIST) | CSF 2.0 six functions + SP 800-53 overview |
| Finance | Ingested | B (SEC EDGAR) | Tickers + companyfacts sample |
| Legal | Ingested | A (Constitution); CourtListener **held** | REST v4 401 without `COURTLISTENER_API_TOKEN`; OpenLaws held |
| HR | Ingested | B/A (DOL public materials); O*NET **held** | Needs `ONET` credentials for Web Services |
| Sales / Marketing | **HOLD** | C pending | Needs Cesar choice: commercial license vs Gravitre-authored |

Evidence: `docs/delivery/knowledge-fabric-ingest-live.json`, 11 chunks with embeddings.

## Phase 3 — Router + hybrid retrieval

- `classify_knowledge_query` — department / jurisdiction / pack / tier
- `retrieve_knowledge_fabric` — FTS + vector + authority rerank
- Live verify: router CA employment → legal+US-CA; authority blog≺NIST; cyber retrieve returns NIST citation

## Phase 4 — Agent create/edit

- `AgentKnowledgePacksEditor` on agent create (step Apps)
- `config.knowledge_packs` + knowledge-assignment POST
- Settings department assign includes `knowledge_pack`
- Orchestrator injects `<knowledge_fabric>` context for `pack.*` assignments

## Phase 5 — Citations

- Provenance `authority_score` via `label_confidence`
- `KnowledgeCitationCard` on decision transparency

## Verification

`docs/delivery/knowledge-fabric-verify-live.json` — `overall_pass: true` @ `2026-08-11T09:31:44Z`

## Decision required (Sales/Marketing)

Do **not** ingest unlicensed blog content. Choose one:
1. **Commercial license (C)** — name the vendor/license, then ingest  
2. **Originally-authored Gravitre content** — then ingest under Gravitre copyright  
3. **Defer** — packs remain HOLD / paused
