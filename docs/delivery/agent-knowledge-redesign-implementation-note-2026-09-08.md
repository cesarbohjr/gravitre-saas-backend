# Agent Knowledge redesign — implementation note (2026-09-08)

## Root cause: "Failed to save knowledge packs"

**Failure path:** `handleSavePacks` → `agentsApi.update({ knowledgePacks })` → `PATCH /api/agents/[id]`.

**Root cause:** `knowledgePacks` / `knowledge_packs` were **not** listed in `handledKeys` in `apps/web/app/api/agents/[id]/route.ts`. Bodies containing only pack selections were proxied to FastAPI instead of merged into Supabase `agents.config.knowledge_packs`, causing PATCH failures and the generic toast.

**Secondary defects (same flow):**
- Assignment POSTs used raw `fetch` without checking `response.ok` (403/409/422 silently ignored).
- No removal of deselected packs from `agent_knowledge_assignments`.
- Dual storage (`config.knowledge_packs` + DB rows) without reconciliation.

**Fix:** Add `knowledgePacks` to handled keys; replace page-level Save with atomic `agentKnowledgeApi.createAssignment` / `deleteAssignment`; remove global save button.

## Domain model mapping (existing architecture — no parallel stack)

| Spec concept | Gravitre implementation |
|--------------|-------------------------|
| KnowledgeBase | `rag_sources` (org-private) + platform `knowledge_sources` / fabric packs |
| KnowledgeSource | `rag_documents` / `rag_chunks` under org sources; fabric `knowledge_documents` for expert packs |
| AgentKnowledgeAssignment | `agent_knowledge_assignments` (unique on org_id + agent_id + source_type + source_id) |

Platform expert packs remain assignment references (`source_type=knowledge_pack`, `source_id=pack.*`) — content is not copied into org storage.

## Affected files

### Fix + API
- `apps/web/app/api/agents/[id]/route.ts` — PATCH handledKeys
- `backend/app/services/knowledge_source_types.py` — `rag_source` type for org corpus assignment

### Frontend
- `apps/web/app/agents/[id]/knowledge/page.tsx` — redesigned workspace
- `apps/web/components/agents/knowledge/*` — tabs, cards, hook, add sheet
- `apps/web/lib/agent-knowledge-assign.ts` — assign helpers + error copy
- `apps/web/app/agents/new/page.tsx` — typed assignment on create

### Tests
- `apps/web/__tests__/lib/agent-knowledge-assign.test.ts`
- `backend/tests/services/test_agent_knowledge_assignment_service.py` (existing)

## Schema / migrations

**None required** for the save fix. Existing `agent_knowledge_assignments` unique constraint supports idempotent assign (409 on duplicate).

Optional future: `knowledge_bases` view/table normalizing `rag_sources` metadata — not introduced in this pass to avoid parallel architecture.

## Test coverage

- Unit: assignment payload + error message formatting
- Regression: PATCH route includes `knowledgePacks` in handled keys (code review + manual)
- Existing: `test_agent_knowledge_assignment_service.py`, assignment service 409 on duplicate

## Verification status

| Step | Status |
|------|--------|
| Root cause identified | PASS — handledKeys omission |
| Atomic assign/remove | Implemented locally |
| Global save removed | Implemented locally |
| Prod browser verification | NOT RUN |
| Cross-tenant denial | Covered by existing `ensure_agent_in_org` + org_id on assignments |
