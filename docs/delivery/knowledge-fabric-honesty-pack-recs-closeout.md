# Citation honesty + department pack recommendations (2026-08-11)

## Phase 1 — content_mode / fetch_status in citations

- Retrieval joins `knowledge_documents.metadata` so existing CISA chunks (doc-level `content_mode=curated_summary_live_html_blocked`) surface without re-ingest
- Provenance + results carry `content_mode` and `fetch_status`
- Orchestrator attaches `knowledge_citations` to explainability; visibility envelope passes them through
- `KnowledgeCitationCard` renders warning-styled badge: **Curated summary — live source fetch was blocked**

Live retrieve evidence: `docs/delivery/knowledge-fabric-honesty-pack-recs-verify.json` (`honesty_pass=true` @ `2026-08-11T21:31:24Z`)

Screenshot: `docs/delivery/knowledge-fabric-honesty-pack-recs-verify.png` (and HTML twin)

## Phase 2 — department pack recommendations

Server correlation (not client duplicate):

- `recommended_pack_ids_for_department()` uses `_PACK_BY_DEPT` + registry `secondary_packs`
- `GET /api/knowledge-fabric/packs?department=Sales` marks + sorts recommended first
- UI: create wizard Apps step + `/agents/[id]/knowledge` pass department into `AgentKnowledgePacksEditor`

Verified:

- Sales → `pack.sales`, `pack.marketing` recommended
- Legal → `pack.legal` recommended
- Full pack list remains toggleable

## Deploy

- Tip: `0d4e226feaa5c14fd6a4ab3e87ce651be21c5ec0`
- Live `GET https://api.gravitre.app/health` → `git_sha=0d4e226feaa5c14fd6a4ab3e87ce651be21c5ec0`
- Post-deploy retrieve still returns CISA `content_mode=curated_summary_live_html_blocked` (`honesty_pass=true`)
